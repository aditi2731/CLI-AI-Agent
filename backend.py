from flask import Flask, request, jsonify, render_template
import os
import subprocess
import sys
from groq import Groq
from dotenv import load_dotenv
import re
import shlex
from datetime import datetime, timedelta
import hashlib
import uuid

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Initialize Groq client with error handling
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    print("WARNING: GROQ_API_KEY not found in environment variables!")
    print("Please create a .env file with your Groq API key.")
    client = None
else:
    try:
        client = Groq(api_key=api_key)
        print("✅ Groq client initialized successfully!")
    except Exception as e:
        print(f"❌ Error initializing Groq client: {e}")
        client = None

BLOCKED_COMMANDS = [
    'rm', 'del', 'format', 'fdisk', 'mkfs',
    'cat', 'type', 'more', 'less', 'head', 'tail',  # File reading commands
    'curl', 'wget', 'ftp', 'scp', 'ssh',  # Network commands
    'net user', 'passwd', 'sudo', 'su',  # User management
    'reg', 'regedit',  # Registry commands
    'powershell', 'cmd', 'bash'  # Shell spawning
]

SENSITIVE_PATHS = [
    r'C:\\Windows\\System32',
    r'C:\\Program Files',
    r'\\etc\\',
    r'\\var\\',
    r'\\root\\',
    r'\\home\\.*\\.ssh',
    r'.*\\.env',
    r'.*\\config',
    r'.*\\password',
    r'.*\\secret'
]

# Session and rate limiting storage
sessions = {}
command_history = {}
rate_limits = {}

class SecurityManager:
    def __init__(self):
        self.max_commands_per_minute = 10
        self.max_session_time = timedelta(hours=2)
        self.cleanup_interval = timedelta(minutes=30)
        self.last_cleanup = datetime.now()
    
    def create_session(self):
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            'created': datetime.now(),
            'last_activity': datetime.now(),
            'command_count': 0
        }
        return session_id
    
    def validate_session(self, session_id):
        if session_id not in sessions:
            return False
        
        session = sessions[session_id]
        if datetime.now() - session['created'] > self.max_session_time:
            del sessions[session_id]
            return False
        
        session['last_activity'] = datetime.now()
        return True
    
    def check_rate_limit(self, session_id):
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        if session_id not in rate_limits:
            rate_limits[session_id] = []
        
        # Remove old entries
        rate_limits[session_id] = [
            timestamp for timestamp in rate_limits[session_id] 
            if timestamp > minute_ago
        ]
        
        if len(rate_limits[session_id]) >= self.max_commands_per_minute:
            return False
        
        rate_limits[session_id].append(now)
        return True
    
    def cleanup_old_sessions(self):
        if datetime.now() - self.last_cleanup < self.cleanup_interval:
            return
        
        expired_sessions = [
            sid for sid, data in sessions.items()
            if datetime.now() - data['last_activity'] > self.max_session_time
        ]
        
        for sid in expired_sessions:
            if sid in sessions:
                del sessions[sid]
            if sid in rate_limits:
                del rate_limits[sid]
        
        self.last_cleanup = datetime.now()

security_manager = SecurityManager()

def is_command_safe(command):
    """Check if command is safe to execute"""
    command_lower = command.lower().strip()
    
    # Check for blocked commands
    for blocked in BLOCKED_COMMANDS:
        if command_lower.startswith(blocked):
            return False, f"Command '{blocked}' is blocked for security reasons"
    
    # Check for sensitive file operations
    for pattern in SENSITIVE_PATHS:
        if re.search(pattern, command, re.IGNORECASE):
            return False, "Access to sensitive system paths is restricted"
    
    # Check for dangerous operators
    dangerous_operators = ['>', '>>', '|', '&', ';', '$(', '`']
    for op in dangerous_operators:
        if op in command:
            return False, f"Operator '{op}' is not allowed for security reasons"
    
    return True, ""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'Server is running!'})

@app.before_request
def before_request():
    # Create session if not exists
    if 'session_id' not in request.headers:
        session_id = security_manager.create_session()
        
    else:
        session_id = request.headers.get('session_id')
        if not security_manager.validate_session(session_id):
            return jsonify({'error': 'Invalid or expired session'}), 401
    
    security_manager.cleanup_old_sessions()

@app.route('/execute', methods=['POST'])
def execute_command():
    session_id = request.headers.get('session_id')
    
    # Rate limiting
    if not security_manager.check_rate_limit(session_id):
        return jsonify({
            'output': '🚫 Rate limit exceeded. Please wait before sending more commands.',
            'error': True,
            'cwd': os.getcwd()
        }), 429
    
    print(f"📥 Received command request: {request.json}")
    data = request.json
    command = data.get('command', '').strip()
    cwd = data.get('cwd', os.getcwd())
    
    if not command:
        return jsonify({'output': '', 'error': False, 'cwd': cwd})
    
    # Security check
    is_safe, error_msg = is_command_safe(command)
    if not is_safe:
        return jsonify({
            'output': f'🚫 Security Error: {error_msg}',
            'error': True,
            'cwd': cwd
        })
    
    try:
        # Handle cd command specially
        if command.lower().startswith('cd '):
            path = command[3:].strip()
            if not path or path == '~':
                new_cwd = os.path.expanduser('~')
            elif path == '..':
                new_cwd = os.path.dirname(cwd)
            elif os.path.isabs(path):
                new_cwd = path
            else:
                new_cwd = os.path.join(cwd, path)
            
            # Check if directory exists
            if os.path.isdir(new_cwd):
                return jsonify({
                    'output': f'Changed directory to {new_cwd}',
                    'error': False,
                    'cwd': os.path.abspath(new_cwd)
                })
            else:
                return jsonify({
                    'output': f'The system cannot find the path specified: {new_cwd}',
                    'error': True,
                    'cwd': cwd
                })
        
        # Handle clear command
        elif command.lower() in ['clear', 'cls']:
            return jsonify({
                'output': 'CLEAR_SCREEN',
                'error': False,
                'cwd': cwd
            })
        
        # Handle other commands
        else:
            # Determine shell based on OS
            if sys.platform.startswith('win'):
                # Windows
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                # Unix-like systems
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            
            # Combine stdout and stderr
            output = result.stdout
            if result.stderr:
                output += result.stderr
            
            # Remove trailing newlines for cleaner display
            output = output.rstrip('\n\r')
            
            return jsonify({
                'output': output or 'Command executed successfully (no output)',
                'error': result.returncode != 0,
                'cwd': cwd
            })
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'output': 'Command timed out (exceeded 30 seconds)',
            'error': True,
            'cwd': cwd
        })
    except FileNotFoundError:
        return jsonify({
            'output': f"'{command.split()[0]}' is not recognized as an internal or external command, operable program or batch file.",
            'error': True,
            'cwd': cwd
        })
    except Exception as e:
        return jsonify({
            'output': f'Error executing command: {str(e)}',
            'error': True,
            'cwd': cwd
        })

@app.route('/analyze', methods=['POST'])
def analyze_terminal():
    print(f"📥 Received analyze request: {request.json}")
    data = request.json
    terminal_output = data.get('output', '')
    
    # Check if the output indicates a security block
    if is_security_blocked_output(terminal_output):
        return jsonify({
            'suggestion': '🔒 Security Policy: This command was blocked for security reasons. Alternative approaches are not provided to maintain system safety.'
        })
    
    # Call AI model to suggest fix for non-security issues
    suggestion = get_ai_suggestion(terminal_output)
    print(f"📤 Sending response: {suggestion}")
    return jsonify({'suggestion': suggestion})

def is_security_blocked_output(output):
    """Check if the output indicates a security-blocked command"""
    if not output:
        return False
    
    security_indicators = [
        "🚫 Security Error:",
        "blocked for security reasons",
        "Access to sensitive system paths is restricted",
        "is not allowed for security reasons"
    ]
    
    return any(indicator in output for indicator in security_indicators)

def get_ai_suggestion(output):
    # Check if client is initialized
    if client is None:
        return "❌ Error: Groq client not initialized. Please check your API key in the .env file."
    
    # Using Groq API with llama model
    try:
        print("🔄 Sending request to Groq API...")
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": """You are a helpful terminal assistant. Analyze the terminal output and suggest the correct command or fix. 
                    
                    IMPORTANT SECURITY RULES:
                    - If the output mentions "Security Error" or "blocked for security reasons", DO NOT provide alternatives
                    - If commands are blocked by security policy, simply acknowledge it's a security measure
                    - Never suggest ways to bypass security restrictions
                    - For legitimate errors (not security blocks), provide helpful suggestions
                    
                    Keep your response concise and actionable. If it's a Windows command prompt error, suggest Windows-specific solutions."""
                },
                {
                    "role": "user",
                    "content": f"Terminal output: {output[:300]}...\nSuggest the correct command or fix:"  # Limit input size for security
                }
            ],
            model="llama3-8b-8192",
            max_tokens=150,
            temperature=0.1,
            timeout=30
        )
        print("✅ Received response from Groq API")
        ai_response = chat_completion.choices[0].message.content.strip()
        
        # Double-check AI response doesn't contain bypass suggestions
        return filter_security_suggestions(ai_response)
    
    except Exception as e:
        error_msg = str(e).lower()
        print(f"❌ Error from Groq API: {e}")
        
        # Handle specific error types
        if "no healthy upstream" in error_msg:
            return "🚫 Groq API is currently unavailable. This might be due to:\n• Invalid API key\n• Service outage\n• Rate limit exceeded\n\nPlease check your API key and try again later."
        elif "unauthorized" in error_msg or "401" in error_msg:
            return "🔑 Authentication failed. Please check if your Groq API key is valid and properly set in the .env file."
        elif "rate limit" in error_msg or "429" in error_msg:
            return "⏱️ Rate limit exceeded. Please wait a moment before trying again."
        elif "timeout" in error_msg:
            return "⏰ Request timed out. The Groq API might be slow. Please try again."
        else:
            return f"❌ Error getting AI suggestion: {str(e)}\n\nPlease check your internet connection and API key."

def filter_security_suggestions(ai_response):
    """Filter out any potential security bypass suggestions from AI response"""
    if not ai_response:
        return ai_response
    
    # Words that might indicate bypass attempts
    bypass_keywords = [
        'bypass', 'workaround', 'alternative', 'instead try', 
        'use this instead', 'try using', 'circumvent', 'avoid'
    ]
    
    # If AI response contains security-related content and bypass keywords
    response_lower = ai_response.lower()
    if any(keyword in response_lower for keyword in bypass_keywords):
        if any(sec_word in response_lower for sec_word in ['security', 'block', 'restrict', 'prevent']):
            return "🔒 Security Policy: This command was blocked for security reasons. No alternative methods will be suggested to maintain system safety."
    
    return ai_response

if __name__ == '__main__':
    print("🚀 Starting Flask server...")
    # Print API key status (masked for security)
    if api_key:
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"🔑 API Key loaded: {masked_key}")
    else:
        print("🔑 No API Key found!")
    
    print(f"📁 Starting directory: {os.getcwd()}")
    app.run(debug=True)

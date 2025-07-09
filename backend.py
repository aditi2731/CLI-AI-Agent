from flask import Flask, request, jsonify, render_template
import os
import subprocess
import sys
from groq import Groq
from dotenv import load_dotenv

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'Server is running!'})

@app.route('/execute', methods=['POST'])
def execute_command():
    print(f"📥 Received command request: {request.json}")
    data = request.json
    command = data.get('command', '').strip()
    cwd = data.get('cwd', os.getcwd())
    
    if not command:
        return jsonify({'output': '', 'error': False, 'cwd': cwd})
    
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
    # Call AI model to suggest fix
    suggestion = get_ai_suggestion(terminal_output)
    print(f"📤 Sending response: {suggestion}")
    return jsonify({'suggestion': suggestion})

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
                    "content": "You are a helpful terminal assistant. Analyze the terminal output and suggest the correct command or fix. Keep your response concise and actionable. If it's a Windows command prompt error, suggest Windows-specific solutions."
                },
                {
                    "role": "user",
                    "content": f"Terminal output: {output}\nSuggest the correct command or fix:"
                }
            ],
            model="llama3-8b-8192",
            max_tokens=150,
            temperature=0.1,
            timeout=30
        )
        print("✅ Received response from Groq API")
        return chat_completion.choices[0].message.content.strip()
    
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

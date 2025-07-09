class CLIAssistant {
    constructor() {
        this.terminal = document.getElementById('terminal');
        this.terminalInput = document.getElementById('terminalInput');
        this.chatContainer = document.getElementById('chatContainer');
        this.chatInput = document.getElementById('chatInput');
        this.statusDot = document.getElementById('statusDot');
        this.statusText = document.getElementById('statusText');
        
        this.commandHistory = [];
        this.historyIndex = -1;
        this.currentDirectory = 'C:\\Users\\aditi\\Desktop\\Project-AI\\CLI-AI-Agent';
        
        this.init();
        this.checkServerStatus();
    }

    init() {
        // Terminal input events
        this.terminalInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                this.executeCommand();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.navigateHistory(-1);
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.navigateHistory(1);
            }
        });

        // Chat input events
        this.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                this.sendMessage();
            }
        });

        // Auto-focus terminal input
        this.terminalInput.focus();
    }

    async checkServerStatus() {
        try {
            const response = await fetch('/health');
            if (response.ok) {
                this.updateStatus(true, 'Connected');
            } else {
                this.updateStatus(false, 'Server Error');
            }
        } catch (error) {
            this.updateStatus(false, 'Disconnected');
        }
    }

    updateStatus(connected, text) {
        this.statusDot.className = connected ? 'status-dot connected' : 'status-dot';
        this.statusText.textContent = text;
    }

    async executeCommand() {
        const command = this.terminalInput.value.trim();
        if (!command) return;

        // Add to history
        this.commandHistory.push(command);
        this.historyIndex = this.commandHistory.length;

        // Display command in terminal
        this.addToTerminal('command', command);
        
        // Clear input
        this.terminalInput.value = '';

        // Execute real command via backend
        const result = await this.executeRealCommand(command);
        
        if (result.error) {
            this.addToTerminal('error', result.output);
            // Auto-analyze error with AI
            await this.analyzeError(result.output);
        } else {
            this.addToTerminal('output', result.output);
        }

        // Update current directory if cd command was successful
        if (command.toLowerCase().startsWith('cd ') && !result.error) {
            this.updateCurrentDirectory(result.cwd || this.currentDirectory);
        }

        // Scroll to bottom
        this.terminal.scrollTop = this.terminal.scrollHeight;
    }

    async executeRealCommand(command) {
        try {
            const response = await fetch('/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    command: command,
                    cwd: this.currentDirectory
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            return result;
        } catch (error) {
            return {
                output: `Error executing command: ${error.message}`,
                error: true
            };
        }
    }

    updateCurrentDirectory(newDir) {
        this.currentDirectory = newDir;
        // Update all prompts to show current directory
        const prompts = this.terminal.querySelectorAll('.prompt');
        const shortPath = this.getShortPath(newDir);
        prompts.forEach(prompt => {
            if (!prompt.closest('.terminal-line').querySelector('.command, .output, .error')) {
                prompt.textContent = `${shortPath}>`;
            }
        });
        
        // Update input container prompt
        const inputPrompt = document.querySelector('.terminal-input-container .prompt');
        if (inputPrompt) {
            inputPrompt.textContent = `${shortPath}>`;
        }
    }

    getShortPath(fullPath) {
        // Shorten very long paths
        if (fullPath.length > 50) {
            const parts = fullPath.split('\\');
            if (parts.length > 3) {
                return `${parts[0]}\\...\\${parts[parts.length-2]}\\${parts[parts.length-1]}`;
            }
        }
        return fullPath;
    }

    async analyzeError(errorOutput) {
        // Show loading message
        const loadingMessage = this.addChatMessage('assistant', 'Analyzing error...', true);

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ output: errorOutput })
            });

            const data = await response.json();
            
            // Remove loading message
            loadingMessage.remove();
            
            // Add AI suggestion
            this.addChatMessage('assistant', data.suggestion);

        } catch (error) {
            // Remove loading message
            loadingMessage.remove();
            
            // Add error message
            this.addChatMessage('assistant', 'Sorry, I couldn\'t analyze the error. Please check if the backend is running.');
        }
    }

    addToTerminal(type, content) {
        const line = document.createElement('div');
        line.className = 'terminal-line';

        const shortPath = this.getShortPath(this.currentDirectory);

        if (type === 'command') {
            line.innerHTML = `<span class="prompt">${shortPath}&gt;</span><span class="command">${content}</span>`;
        } else {
            line.innerHTML = `<span class="${type}">${content}</span>`;
        }

        // Remove cursor from previous line
        const cursor = this.terminal.querySelector('.cursor');
        if (cursor) cursor.remove();

        this.terminal.appendChild(line);

        // Add new cursor line
        const cursorLine = document.createElement('div');
        cursorLine.className = 'terminal-line';
        cursorLine.innerHTML = `<span class="prompt">${shortPath}&gt;</span><span class="cursor">_</span>`;
        this.terminal.appendChild(cursorLine);

        // Smooth scroll to bottom
        this.terminal.scrollTo({
            top: this.terminal.scrollHeight,
            behavior: 'smooth'
        });
    }

    navigateHistory(direction) {
        if (this.commandHistory.length === 0) return;

        this.historyIndex += direction;
        
        if (this.historyIndex < 0) {
            this.historyIndex = 0;
        } else if (this.historyIndex >= this.commandHistory.length) {
            this.historyIndex = this.commandHistory.length;
            this.terminalInput.value = '';
            return;
        }

        this.terminalInput.value = this.commandHistory[this.historyIndex];
    }

    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message) return;

        // Add user message
        this.addChatMessage('user', message);
        
        // Clear input
        this.chatInput.value = '';

        // Show loading
        const loadingMessage = this.addChatMessage('assistant', 'Thinking...', true);

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ output: message })
            });

            const data = await response.json();
            
            // Remove loading message
            loadingMessage.remove();
            
            // Add AI response
            this.addChatMessage('assistant', data.suggestion);

        } catch (error) {
            // Remove loading message
            loadingMessage.remove();
            
            // Add error message
            this.addChatMessage('assistant', 'Sorry, I couldn\'t process your message. Please check if the backend is running.');
        }
    }

    addChatMessage(sender, content, isLoading = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = sender === 'user' ? '👤' : '🤖';

        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';

        if (isLoading) {
            messageContent.innerHTML = `
                <div class="loading">
                    <div class="loading-dot"></div>
                    <div class="loading-dot"></div>
                    <div class="loading-dot"></div>
                </div>
            `;
        } else {
            const p = document.createElement('p');
            p.textContent = content;
            messageContent.appendChild(p);
        }

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageContent);

        this.chatContainer.appendChild(messageDiv);
        
        // Smooth scroll to bottom
        this.chatContainer.scrollTo({
            top: this.chatContainer.scrollHeight,
            behavior: 'smooth'
        });

        return messageDiv;
    }

    clearTerminal() {
        const shortPath = this.getShortPath(this.currentDirectory);
        this.terminal.innerHTML = `<div class="terminal-line"><span class="prompt">${shortPath}&gt;</span><span class="cursor">_</span></div>`;
    }

    clearChat() {
        this.chatContainer.innerHTML = `
            <div class="message assistant-message">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    <p>Hello! I'm your CLI AI Assistant. I'll help you fix terminal errors and suggest the right commands. Try running a command in the terminal!</p>
                </div>
            </div>
        `;
    }
}

// Global functions for button clicks
function clearTerminal() {
    window.cliAssistant.clearTerminal();
}

function clearChat() {
    window.cliAssistant.clearChat();
}

function sendMessage() {
    window.cliAssistant.sendMessage();
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.cliAssistant = new CLIAssistant();
});
# CLI AI Agent - Your Smart Terminal Companion

### What does it actually do?
It's basically a web-based terminal that has an AI buddy sitting right next to it. When you run commands and something breaks the AI automatically jumps in and explains what went wrong and how to fix it.

### Features:-
* Real terminal: Not just a fake simulation - it actually runs your commands.
* Smart AI helper: Uses Groq's super fast AI to analyze errors and suggest fixes.
* Split screen: Terminal on the left, AI chat on the right - no more switching between tabs.
* Command history: Arrow keys work just like in a real terminal.
* Actually useful suggestions: The AI understands context and gives practical advice.

  ### How I built it:
  I used Flask for the backend because it's simple and gets the job done. The frontend is just vanilla HTML, CSS, and JavaScript.The AI part uses Groq's API .

  ### Why might you find this useful?
  - You're learning command line stuff and need help.
  - You work with terminals daily and want faster error resolution.
  - You're tired of context-switching between terminal and browser.
  - You want to see what modern AI can do with terminal assistance.
 
 ### Added Features:
 #### Command Filtering-
 * What it does: Before allowing any command to run, it checks if the command is safe.
 * How it works:
  -	Maintains a "blacklist" of dangerous commands (like rm, del, format)
	- Blocks access to sensitive folders (like Windows system files, password files)
	- Prevents dangerous operators like > (which can overwrite files) or | (which can chain dangerous commands)

  #### Session Management -
  * What it does: Controls how long someone can use the system and how fast they can send commands.
  * How it works:
   -	Sessions: Each user gets a temporary ID that expires after 2 hours
   - Rate Limiting: Prevents someone from sending 100 commands per second (which could be an attack)
   -	Cleanup: Automatically removes old sessions to free up memory



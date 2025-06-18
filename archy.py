import json
import os
import pyperclip
from pprint import pprint
import collections.abc

# --- Configuration ---
STATE_FILE_PATH = "project_state.json"

# --- System Prompt for the AI ---
SYSTEM_PROMPT = """
You are "Archy," an expert AI software architect and developer. Your sole purpose is to collaborate with a user to transform a project plan into a complete, production-ready codebase. You are methodical, precise, and security-conscious.

--- Core Principles ---
1.  **Stateful Interaction**: You operate on a `projectState` JSON object provided in the prompt. Your response MUST be a single JSON object containing a `stateUpdate` that will be merged back into the project state.
2.  **Command-Driven Workflow**: You respond to user commands. Your response should include a `message` field to guide the user to the next logical command.
3.  **Structured Output**: ALL of your output must be a single, self-contained JSON object following the specified schema: `{ "status": "...", "message": "...", "stateUpdate": { ... } }`. Do not add any conversational text outside of this JSON.

--- The Workflow: PLAN -> SPECIFY -> CODE -> REFINE ---
1.  **PLAN**: Analyze the user's request and output a `projectState.plan` object containing milestones and tasks. Each task must have a unique ID (e.g., "M1-T1").
2.  **SPECIFY**: Detail a milestone's tasks, describing purpose, inputs, outputs, file structure, and dependencies. This populates `projectState.specifications[Milestone-ID]`.
3.  **CODE**: Generate code files for a single task. This populates `projectState.code[Task-ID]`.
4.  **REFINE**: Apply user-provided instructions to modify an existing plan, spec, or code artifact. The relevant artifact will be provided in the context.

--- Quality & Security Gates (NON-NEGOTIABLE) ---
When generating code (`code <ID>` or `refine <ID>`):
- **File Object Schema**: Each entry in the `files` array MUST be a JSON object with exactly two keys: a `path` key (string) containing the full relative path for the file, and a `content` key (string) containing the entire file content. Do not use 'name' or any other keys for the file path.
- **Security**: Never hardcode secrets. Use placeholders like `os.environ.get("API_KEY")` and state they must be managed via environment variables. All database queries MUST use parameterized statements. Sanitize all user-facing inputs.
- **Error Handling**: Include robust error handling (e.g., try-except blocks) for I/O, network calls, etc.
- **Readability**: Code must be well-commented with clear docstrings (purpose, args, returns). Adhere to language-specific style guides (e.g., PEP 8 for Python).
- **Testing**: For each functional code file, provide a corresponding test file covering at least one success and one failure/edge case. The test file should be included in the `files` array of the same response.
- **Dependencies**: Do NOT invent version numbers. Provide a single shell command string to install dependencies (e.g., `pip install flask pytest`). Include this command in the `stateUpdate` for the relevant task under the `dependencies` key.

--- User Commands ---
You will respond to the following commands from the user. Client-side commands are listed for your awareness.
- `plan <description>`: Creates a new project plan.
- `specify <Milestone-ID>`: Generates specifications for all tasks in a milestone.
- `code <Task-ID>`: Generates code and tests for a single task.
- `refine <ID> <instruction>`: Modifies an existing plan, spec, or code artifact based on the instruction.
- `generate_readme`: Generates a `README.md` file for the project. Place the full markdown content in the `stateUpdate` object under a single key named `readme`.
- (Client-side) `sync <Task-ID|all>`: User command to manually recreate files from the project state on disk.
- (Client-side) `show_plan`: Displays the current project plan.
- (Client-side) `show_spec <Milestone-ID>`: Displays the specification for a milestone.
- (Client-side) `show_code <Task-ID>`: Displays the code for a task.
"""

# --- State Management ---
def load_state():
    """Loads the project state from the JSON file."""
    if os.path.exists(STATE_FILE_PATH):
        try:
            with open(STATE_FILE_PATH, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"[System] Warning: Could not parse '{STATE_FILE_PATH}'. Starting with a fresh state.")
            return {}
    return {
        "plan": None,
        "specifications": {},
        "code": {}
    }

def save_state(state):
    """Saves the project state to the JSON file."""
    dir_name = os.path.dirname(STATE_FILE_PATH)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with open(STATE_FILE_PATH, 'w') as f:
        json.dump(state, f, indent=2)

project_state = load_state()

def deep_merge(source, destination):
    """Recursively merge source dict into destination dict."""
    for key, value in source.items():
        if isinstance(value, collections.abc.Mapping):
            destination[key] = deep_merge(value, destination.get(key, {}))
        else:
            destination[key] = value
    return destination

# --- LLM Interaction ---
def generate_prompt_for_user(user_command):
    """Constructs a context-aware prompt, prints it, and copies it to the clipboard."""
    command_parts = user_command.split(maxsplit=1)
    command = command_parts[0].lower()
    args = command_parts[1] if len(command_parts) > 1 else ""

    context_state = {"plan": project_state.get("plan")}

    if command in ['specify', 'code', 'refine']:
        if not args:
            print(f"[System] The '{command}' command requires an ID. e.g., '{command} M1-T1 <instruction>'")
            return None
        target_id = args.split()[0]
        milestone_id = target_id.split('-')[0]
        task_id = target_id if '-' in target_id else None

        # For any of these commands, the milestone spec is useful context
        if project_state.get("specifications", {}).get(milestone_id):
            context_state['specifications'] = {milestone_id: project_state["specifications"][milestone_id]}

        # For 'code' or 'refine' of a task, include the existing code
        if task_id and project_state.get("code", {}).get(task_id):
            context_state.setdefault('code', {})[task_id] = project_state["code"][task_id]

    elif command == 'generate_readme':
        # README command needs all specifications for a full overview
        context_state['specifications'] = project_state.get("specifications")

    prompt = f"""{SYSTEM_PROMPT}

--- Current Project State (Context) ---
{json.dumps(context_state, indent=2)}

--- User Command ---
{user_command}
"""
    print("\n--- PROMPT FOR MANUAL EXECUTION (Copied to Clipboard) ---")
    print(prompt)
    print("-------------------------------------------------------------")
    try:
        pyperclip.copy(prompt)
        print("[System] Prompt has been copied to your clipboard.")
    except pyperclip.PyperclipException:
        print("[System] Could not copy to clipboard. Please install 'pyperclip' or copy the prompt manually.")
    
    return prompt

# --- File Operations ---
def save_files_from_update(code_update, task_id, force_save=False):
    """Saves generated files to disk, prompting the user unless forced."""
    if not code_update or not code_update.get('files'):
        print(f"[System] No file information found for task {task_id}.")
        return

    output_dir = "generated_project"
    choice = 'y' if force_save else ''
    
    if not force_save:
        print(f"\n[System] Files for task '{task_id}' will be saved in '{output_dir}/':")
        # Loop for displaying files
        for file in code_update['files']:
            # FIX: Check for 'path' OR 'name' key
            file_path = file.get('path') or file.get('name')
            if isinstance(file, dict) and file_path:
                full_path_for_display = os.path.join(output_dir, *file_path.split('/'))
                print(f"  - {full_path_for_display}")
            else:
                print(f"[System] Warning: Skipping an invalid file entry in task '{task_id}'.")
        
        if code_update.get('dependencies'):
            print(f"\nInstall dependencies with: `{code_update['dependencies']}`")

        choice = input(f"Do you want to save/overwrite these files? (y/N): ").lower()

    if choice == 'y':
        # Loop for saving files
        for file in code_update['files']:
            file_path = file.get('path') or file.get('name')
            if isinstance(file, dict) and file_path and 'content' in file:
                output_dir_abs = os.path.abspath(output_dir)
                final_path_abs = os.path.abspath(os.path.join(output_dir_abs, file_path))

                if not final_path_abs.startswith(output_dir_abs):
                    print(f"[System] Security Warning: Skipping file with malicious path: {file_path}")
                    continue
                
                os.makedirs(os.path.dirname(final_path_abs), exist_ok=True)
                
                with open(final_path_abs, 'w', encoding='utf-8') as f:
                    f.write(file['content'])
                print(f"  Saved {final_path_abs}")
                
        print(f"[System] Files for {task_id} saved.")
    else:
        print(f"[System] File save for task '{task_id}' skipped.")

def save_readme(content):
    """Saves the README.md file."""
    output_dir = "generated_project"
    os.makedirs(output_dir, exist_ok=True)
    readme_path = os.path.join(output_dir, "README.md")
    print(f"\n[System] A new README.md is available.")
    choice = input("Do you want to save/overwrite the README.md file? (y/N): ").lower()
    if choice == 'y':
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[System] Saved {readme_path}")
    else:
        print("[System] README.md save skipped.")

# --- Main Application Loop ---
def main():
    """The main REPL for interacting with Archy."""
    print("Welcome to Archy AI Developer Co-pilot.")
    if os.path.exists(STATE_FILE_PATH):
        print(f"[System] Resumed project from '{STATE_FILE_PATH}'")
    else:
        print("[System] No existing project found. A new one will be created.")
        print("Type 'plan <your project idea>' to start.")
    
    print("Type 'help' for a list of commands, or 'exit' to quit.")

    while True:
        user_input = input("\n> ")
        if not user_input:
            continue
        
        command_parts = user_input.split(maxsplit=1)
        command = command_parts[0].lower()
        args = command_parts[1] if len(command_parts) > 1 else ""

        if command == 'exit':
            break
        elif command == 'help':
            print("""
Available Commands:
- plan <description>         : Creates a new project plan.
- specify <Milestone-ID>     : Generates specifications for a milestone.
- code <Task-ID>             : Generates code and tests for a task.
- refine <ID> <instruction>  : Modifies a plan, spec, or code.
- generate_readme            : Creates a README.md from the project state.
- sync <Task-ID|all>         : Recreates files from the project state on disk.
- show_plan                  : Displays the current project plan.
- show_spec <Milestone-ID>   : Displays the specification for a milestone.
- show_code <Task-ID>        : Displays the code for a task.
- exit                       : Quits the application.
            """)
            continue
        
        # --- Commands that don't need the LLM ---
        if command == 'show_plan':
            pprint(project_state.get('plan', "No plan found."))
            continue
        elif command == 'show_spec':
            if not args:
                print("[System] Usage: show_spec <Milestone-ID>")
                continue
            pprint(project_state.get('specifications', {}).get(args, "Specification not found."))
            continue
        elif command == 'show_code':
            if not args:
                print("[System] Usage: show_code <Task-ID>")
                continue
            pprint(project_state.get('code', {}).get(args, "Code not found."))
            continue
        elif command == 'sync':
            if not args:
                print("[System] Usage: sync <Task-ID | all>")
                continue
            
            if args.lower() == 'all':
                if not project_state.get('code'):
                    print("[System] No code found in the project state to sync.")
                    continue
                
                print("[System] This will overwrite all project files on disk with the current state.")
                choice = input("Do you want to proceed? (y/N): ").lower()
                if choice != 'y':
                    print("[System] Sync canceled.")
                    continue

                print("[System] Syncing all tasks...")
                for task_id, code_block in project_state.get('code', {}).items():
                    save_files_from_update(code_block, task_id, force_save=True)
                print("[System] All tasks synced.")
            else:
                code_block = project_state.get('code', {}).get(args)
                if code_block:
                    save_files_from_update(code_block, args, force_save=False)
                else:
                    print(f"[System] Code for task '{args}' not found. Use `code {args}` to generate it.")
            continue

        # --- Commands that require the LLM ---
        if generate_prompt_for_user(user_input) is None:
            continue
        
        print("\n[System] Paste the LLM's JSON response below and press Enter (or Ctrl+D/Ctrl+Z+Enter to finish):")
        
        response_str = ""
        try:
            # Simple multi-line input reading
            lines = []
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            response_str = "\n".join(lines)

        if not response_str.strip():
            print("[System] No response received. Aborting command.")
            continue
        
        try:
            if response_str.strip().startswith("```json"):
                response_str = response_str.strip()[7:-4].strip()
            
            response_json = json.loads(response_str)
        except json.JSONDecodeError:
            print("[System] Error: Invalid JSON response received. Ensure you copy only the JSON object.")
            print("--- Received Text ---\n" + response_str + "\n-----------------------")
            continue
        
        print(f"\n[Archy] {response_json.get('message', 'No message received.')}")

        if response_json.get('status', '').lower() == 'success' and 'stateUpdate' in response_json:
            update_data = response_json['stateUpdate']

            # Validate the structure before merging
            if 'code' in update_data and not isinstance(update_data['code'], dict):
                print("[System] Error: Received malformed 'code' update. State will not be updated.")
                continue
            if 'specifications' in update_data and not isinstance(update_data['specifications'], dict):
                print("[System] Error: Received malformed 'specifications' update. State will not be updated.")
                continue

            deep_merge(update_data, project_state)
            save_state(project_state)
            print(f"[System] Project state updated and saved to '{STATE_FILE_PATH}'")
            
            # --- Automatic File Syncing Logic ---
            if 'code' in update_data:
                updated_task_ids = update_data['code'].keys()
                print(f"[System] Code was modified for: {', '.join(updated_task_ids)}. Checking for file sync...")
                for task_id in updated_task_ids:
                    save_files_from_update(project_state['code'][task_id], task_id)
            
            if 'readme' in update_data:
                save_readme(update_data['readme'])

        else:
            print("[System] The AI indicated the request could not be completed successfully. Project state was not changed.")

if __name__ == '__main__':
    main()
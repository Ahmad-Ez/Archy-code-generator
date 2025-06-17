import json
import os
import pyperclip
from pprint import pprint
import collections.abc

# --- Configuration ---
STATE_FILE_PATH = "project_state.json"

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
4.  **REFINE**: Apply user-provided instructions to modify an existing plan, spec, or code artifact.

--- Quality & Security Gates (NON-NEGOTIABLE) ---
When generating code (`code <ID>`):
- **Security**: Never hardcode secrets. Use placeholders like `os.environ.get("API_KEY")` and state they must be managed via environment variables. All database queries MUST use parameterized statements. Sanitize all user-facing inputs.
- **Error Handling**: Include robust error handling (e.g., try-except blocks) for I/O, network calls, etc.
- **Readability**: Code must be well-commented with clear docstrings (purpose, args, returns). Adhere to language-specific style guides (e.g., PEP 8 for Python).
- **Testing**: For each functional code file, provide a corresponding test file covering at least one success and one failure/edge case.
- **Dependencies**: Do NOT invent version numbers. Provide a shell command to install dependencies (e.g., `pip install flask pytest`). Include this command in the `stateUpdate` for the relevant task.

--- User Commands ---
You will respond to the following commands:
- `plan <description>`: Creates a new project plan.
- `specify <Milestone-ID>`: Generates specifications for all tasks in a milestone.
- `code <Task-ID>`: Generates code and tests for a single task.
- `refine <ID> <instruction>`: Modifies an existing plan, spec, or code artifact based on the instruction.
- `generate_readme`: Generates a `README.md` file for the project based on the full plan and specifications.
- `show_plan`: Displays the current project plan.
- `show_spec <Milestone-ID>`: Displays the specification for a milestone.
- `show_code <Task-ID>`: Displays the code for a task.
"""

# --- State Management ---
def load_state():
    """Loads the project state from the JSON file."""
    if os.path.exists(STATE_FILE_PATH):
        with open(STATE_FILE_PATH, 'r') as f:
            return json.load(f)
    return {
        "plan": None,
        "specifications": {},
        "code": {}
    }

def save_state(state):
    """Saves the project state to the JSON file."""
    os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
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
    """Constructs the full prompt, prints it, and copies it to the clipboard."""
    context_state = {
        "plan": project_state.get("plan"),
        # To optimize context size, you could selectively add specifications
        # for milestones relevant to the current command.
    }

    prompt = f"""{SYSTEM_PROMPT}

--- Current Project State (Context) ---
{json.dumps(context_state, indent=2)}

--- User Command ---
{user_command}
"""
    print("--- PROMPT FOR MANUAL EXECUTION (Copied to Clipboard) ---")
    print(prompt)
    print("-------------------------------------------------------------")
    try:
        pyperclip.copy(prompt)
        print("[System] Prompt has been copied to your clipboard.")
    except pyperclip.PyperclipException:
        print("[System] Could not copy to clipboard. Please install 'pyperclip' (`pip install pyperclip`) or copy the prompt manually.")
    
    return prompt

# --- File Operations ---
def save_files_from_update(code_update, task_id_for_message=""):
    """Prompts the user to save generated files to the disk inside a 'generated_project' directory."""
    if not code_update or not code_update.get('files'):
        print(f"[System] No file information found for task {task_id_for_message}.")
        return

    output_dir = "generated_project"

    print(f"\n[System] Files for task '{task_id_for_message}' will be saved in '{output_dir}/':")
    for file in code_update['files']:
        full_path_for_display = os.path.join(output_dir, *file['path'].split('/'))
        print(f"  - {full_path_for_display}")
    
    if code_update.get('dependencies'):
        print(f"\nInstall dependencies with: `{code_update['dependencies']}`")

    choice = input(f"Do you want to save/overwrite the files for '{task_id_for_message}'? (y/N): ").lower()
    if choice == 'y':
        for file in code_update['files']:
            relative_path = os.path.join(*file['path'].split('/'))
            final_path = os.path.join(output_dir, relative_path)
            
            content = file['content']
            
            if os.path.dirname(final_path):
                os.makedirs(os.path.dirname(final_path), exist_ok=True)
            
            with open(final_path, 'w') as f:
                f.write(content)
            print(f"  Saved {final_path}")
        print(f"[System] Files for {task_id_for_message} saved.")

# --- Main Application Loop ---
def main():
    """The main REPL for interacting with Archy."""
    print("Welcome to Archy AI Developer Co-pilot.")
    if os.path.exists(STATE_FILE_PATH):
        # MODIFIED: Updated user message for new file path
        print(f"[System] Resumed project from '{STATE_FILE_PATH}'")
    else:
        print("[System] No existing project found. A new one will be created.")
        print("Type 'plan <your project idea>' to start.")
    
    print("Type 'help' for a list of commands, or 'exit' to quit.")

    while True:
        user_input = input("\n> ")
        if not user_input:
            continue
        
        command_parts = user_input.split()
        command = command_parts[0].lower()

        if command == 'exit':
            break
        elif command == 'help':
            print("""
Available Commands:
- plan <description>         : Creates a new project plan.
- specify <Milestone-ID>     : Generates specifications for a milestone.
- code <Task-ID>             : Generates code and tests for a task.
- sync <Task-ID|all>         : Recreates files from the project state on disk.
- show_plan                  : Displays the current project plan.
- show_spec <Milestone-ID>   : Displays the specification for a milestone.
- show_code <Task-ID>        : Displays the code for a task.
- exit                       : Quits the application.
            """)
            continue
        
        # --- Commands that don't need the LLM ---
        if command == 'show_plan':
            pprint(project_state['plan'])
            continue
        elif command == 'show_spec':
            if len(command_parts) < 2:
                print("[System] Usage: show_spec <Milestone-ID>")
                continue
            spec_id = command_parts[1]
            pprint(project_state['specifications'].get(spec_id, "Specification not found."))
            continue
        elif command == 'show_code':
            if len(command_parts) < 2:
                print("[System] Usage: show_code <Task-ID>")
                continue
            code_id = command_parts[1]
            pprint(project_state['code'].get(code_id, "Code not found."))
            continue
        elif command == 'sync':
            if len(command_parts) < 2:
                print("[System] Usage: sync <Task-ID | all>")
                continue
            
            target = command_parts[1]
            if target.lower() == 'all':
                if not project_state.get('code'):
                    print("[System] No code found in the project state to sync.")
                    continue
                print("[System] Syncing all tasks...")
                for task_id, code_block in project_state['code'].items():
                    save_files_from_update(code_block, task_id)
                print("[System] All tasks synced.")
            else:
                task_id = target
                code_block = project_state.get('code', {}).get(task_id)
                if code_block:
                    save_files_from_update(code_block, task_id)
                else:
                    print(f"[System] Code for task '{task_id}' not found in project state. Use `code {task_id}` to generate it first.")
            continue


        # --- Commands that require the LLM ---
        generate_prompt_for_user(user_input)
        
        # --- Wait for the user to paste the LLM's response ---

        print("\n[System] Paste the LLM's JSON response below and press Enter (or Ctrl+D/Ctrl+Z+Enter to finish):")
        
        response_str = ""
        try:
            for line in iter(input, "END_OF_JSON"):
                response_str += line
        except (EOFError, KeyboardInterrupt):
            pass

        if not response_str.strip():
            print("[System] No response received. Aborting command.")
            continue
        
        try:
            # Clean up the response in case it's wrapped in markdown
            if response_str.strip().startswith("```json"):
                response_str = response_str.strip()[7:-4].strip()
            
            response_json = json.loads(response_str)
        except json.JSONDecodeError:
            print("[System] Error: Invalid JSON response received. Please ensure you copy only the JSON object.")
            print("--- Received Text ---")
            print(response_str)
            print("-----------------------")
            continue
        
        print(f"\n[Archy] {response_json.get('message', 'No message received.')}")

        if response_json.get('status') == 'success' and 'stateUpdate' in response_json:
            deep_merge(response_json['stateUpdate'], project_state)
            save_state(project_state)
            # MODIFIED: Updated user message for new file path
            print(f"[System] Project state updated and saved to '{STATE_FILE_PATH}'")
            
            if command == 'code':
                task_id = command_parts[1]
                code_update = response_json.get('stateUpdate', {}).get('code', {}).get(task_id)
                if code_update:
                    save_files_from_update(code_update, task_id)
                else:
                    print("[System] Code update not found in the expected format in the response.")

if __name__ == '__main__':
    main()
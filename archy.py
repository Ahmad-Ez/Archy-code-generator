import json
import os
import pyperclip
from pprint import pprint
import collections.abc
import shutil
import fnmatch

# --- Global Configuration for Archy ---
# This config is for the tool itself, not a specific project.
ARCHY_CONFIG_PATH = "archy_config.json"
MAX_RECENT_PROJECTS = 10

# --- Project-Specific Configuration (Dynamically Determined) ---
# These will be set after the user selects a project.
STATE_FILE_NAME = "project_state.json"
CHECKPOINT_DIR_NAME = ".archy/checkpoints"

# --- Global State Variables (Initialized in main) ---
project_path = None # Will be set after project selection
project_state = {}  # Will be loaded after project selection

# --- System Prompt for the AI ---
# Enforces a more robust, dictionary-based plan structure.
SYSTEM_PROMPT = """
You are "Archy," an expert AI software architect and developer. Your sole purpose is to collaborate with a user to transform a project plan into a complete, production-ready codebase. You are methodical, precise, and security-conscious.

--- Core Principles ---
1.  **Stateful Interaction**: You operate on a `projectState` JSON object provided in the prompt. Your response MUST be a single JSON object containing a `stateUpdate` that will be merged back into the project state.
2.  **Global Configuration**: If a `projectConfig` object is provided, you should use the values within it (e.g., projectName, author) to inform your generated code, comments, and documentation.
3.  **Structured Output**: ALL of your output must be a single, self-contained JSON object following the specified schema: `{ "status": "...", "message": "...", "stateUpdate": { ... } }`.

--- The Workflow: PLAN -> SPECIFY -> CODE -> REFINE ---
1.  **PLAN**: Analyze the user's request and output a `projectState.plan` object. This object MUST contain a `milestones` dictionary.
2.  **SPECIFY**: Detail a milestone's tasks, describing purpose, file structure, etc. This populates `projectState.specifications`.
3.  **CODE**: Generate code files for a single task. This populates `projectState.code`.
4.  **REFINE**: Apply user-provided instructions to modify an existing plan, spec, or code artifact.

--- State Structure Guide ---
This is an example of the target `projectState` structure you will be building. Note the consistent use of dictionaries keyed by IDs, with no redundant "id" fields inside the objects.

{
  "plan": {
    "milestones": {
      "M1": {
        "description": "High-level goal for the first milestone.",
        "tasks": {
          "M1-T1": "Description for the first task.",
          "M1-T2": "Description for the second task."
        }
      }
    }
  },
  "specifications": {
    "M1": {
      "M1-T1": {
        "title": "Title of the first task",
        "purpose": "What this task aims to achieve.",
        "file_structure": ["path/to/new_file.py", "path/to/test_file.py"],
        "acceptance_criteria": ["The main function runs without error."]
      }
    }
  },
  "code": {
    "M1-T1": {
      "dependencies": "pip install pandas",
      "files": {
        "path/to/new_file.py": "import pandas as pd\\n\\ndef main():\\n    print(\\"Hello, world!\\")",
        "path/to/test_file.py": "from new_file import main\\n\\ndef test_main():\\n    assert main is not None"
      }
    }
  }
}

--- IMPORTANT: Handling Existing Files ---
If the prompt includes an `EXISTING_FILES_TO_MODIFY` section, your primary goal is to intelligently merge the new requirements into the existing code.
- DO NOT remove existing functionality unless specifically told to.
- Your generated `content` for that file should be a complete, new version of the file that incorporates both the old and new logic.
- Ensure the final code is syntactically correct and coherent.

--- Quality & Security Gates (NON-NEGOTIABLE) ---
When generating code (`code <ID>` or `refine <ID>`):
- **File Object Schema**: The `files` key MUST be a JSON object. Each key within this object is the full relative `path` (string) for a file, and its value is the entire file `content` (string).
- **Security**: Never hardcode secrets. Use placeholders like `os.environ.get("API_KEY")` and state they must be managed via environment variables. All database queries MUST use parameterized statements. Sanitize all user-facing inputs.
- **Error Handling**: Include robust error handling (e.g., try-except blocks) for I/O, network calls, etc.
- **Readability**: Code must be well-commented with clear docstrings (purpose, args, returns). Adhere to language-specific style guides (e.g., PEP 8 for Python).
- **Testing**: For each functional code file, provide a corresponding test file covering at least one success and one failure/edge case. The test file should be included in the `files` object of the same response.
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

# --- NEW: Global Archy Config Management ---
def load_archy_config():
    """Loads the main archy config file with recent projects."""
    if not os.path.exists(ARCHY_CONFIG_PATH):
        return {"recent_projects": []}
    try:
        with open(ARCHY_CONFIG_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"recent_projects": []}

def save_archy_config(config):
    """Saves the main archy config file."""
    with open(ARCHY_CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

def update_recent_projects(selected_path):
    """Adds a project path to the top of the recent projects list."""
    config = load_archy_config()
    recent_projects = config.get("recent_projects", [])

    # If path exists, remove it to re-add it to the top
    if selected_path in recent_projects:
        recent_projects.remove(selected_path)
    recent_projects.insert(0, selected_path)
    # Trim the list to the max allowed length

    config["recent_projects"] = recent_projects[:MAX_RECENT_PROJECTS]
    save_archy_config(config)

def select_project_path():
    """Prompts the user to select a recent project or enter a new path."""
    config = load_archy_config()
    recent_projects = config.get("recent_projects", [])
    print("\n[Archy] Select a project or provide a new path.")
    for i, path in enumerate(recent_projects, 1):
        print(f"  {i}. {path}")
    while True:
        choice = input(f"\nEnter a number, a new project path, or 'exit': ")
        if choice.lower() == 'exit':
            return None
        try:
            # Try to interpret as a number first
            choice_num = int(choice)
            if 1 <= choice_num <= len(recent_projects):
                selected_path = recent_projects[choice_num - 1]
                break
            else:
                print("[System] Invalid number. Please try again.")
        except ValueError:
            # If it's not a number, treat as a path
            selected_path = os.path.abspath(choice)
            break

    # SUGGESTION: Handle Path vs. Directory in Project Selection
    if os.path.exists(selected_path):
        if not os.path.isdir(selected_path):
            print(f"[System] Error: The path '{selected_path}' points to a file, not a directory.")
            return None
    else:
        print(f"[System] The directory '{selected_path}' does not exist.")
        create = input("Do you want to create it? (y/N): ").lower()
        if create == 'y':
            os.makedirs(selected_path)
            print(f"[System] Created project directory: '{selected_path}'")
        else:
            print("[System] Project selection canceled.")
            return None

    update_recent_projects(selected_path)
    print(f"[System] Using project directory: '{selected_path}'")
    return selected_path

# --- State Management (uses global project_path) ---
def load_state():
    """Loads the project state from the JSON file within the project directory."""
    state_file_path = os.path.join(project_path, ".archy", STATE_FILE_NAME)
    if os.path.exists(state_file_path):
        try:
            with open(state_file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"[System] Warning: Could not parse '{state_file_path}'. Starting with a fresh state.")
            return {}
    return {
        "plan": None,
        "specifications": {},
        "code": {},
        "projectConfig": {},
        "aggregatedDependencies": {"pip": [], "npm": []}
    }

def save_state():
    """Saves the project state to the JSON file within the project directory."""
    state_file_path = os.path.join(project_path, ".archy", STATE_FILE_NAME)
    os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
    with open(state_file_path, 'w') as f:
        json.dump(project_state, f, indent=2)

def deep_merge(source, destination):
    """Recursively merges source dict into destination dict."""
    for key, value in source.items():
        if isinstance(value, dict):
            # Get the destination value, or an empty dict if the key doesn't exist or is None
            node = destination.get(key)
            if not isinstance(node, dict):
                node = {}
            destination[key] = deep_merge(value, node)
        else:
            destination[key] = value
    return destination

# --- Checkpoint and Undo Functionality (uses global project_path) ---
def save_checkpoint(name):
    """Saves the current project state as a checkpoint in the project directory."""
    state_file_path = os.path.join(project_path, ".archy", STATE_FILE_NAME)
    checkpoint_dir = os.path.join(project_path, CHECKPOINT_DIR_NAME)
    if not os.path.exists(state_file_path):
        print("[System] No project state to save a checkpoint for.")
        return False
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = os.path.join(checkpoint_dir, f"{name}.json")
    try:
        shutil.copyfile(state_file_path, checkpoint_path)
        # SUGGESTION: Improved comment clarity
        if name != ".undo": # Don't print a confirmation message for automatic undo checkpoints
             print(f"[System] Checkpoint '{name}' saved successfully.")
        return True
    except Exception as e:
        print(f"[System] Error saving checkpoint '{name}': {e}")
        return False

def revert_to_checkpoint(name):
    """Reverts the project state to a named checkpoint."""
    global project_state
    state_file_path = os.path.join(project_path, ".archy", STATE_FILE_NAME)
    checkpoint_dir = os.path.join(project_path, CHECKPOINT_DIR_NAME)
    checkpoint_path = os.path.join(checkpoint_dir, f"{name}.json")
    if not os.path.exists(checkpoint_path):
        print(f"[System] Error: Checkpoint '{name}' not found.")
        return False
    try:
        shutil.copyfile(checkpoint_path, state_file_path)
        project_state = load_state() # Reload state from the reverted file
        print(f"[System] Project state successfully reverted to checkpoint '{name}'.")
        return True
    except Exception as e:
        print(f"[System] Error reverting to checkpoint '{name}': {e}")
        return False

def list_checkpoints():
    """Lists all available checkpoints for the current project."""
    checkpoint_dir = os.path.join(project_path, CHECKPOINT_DIR_NAME)
    if not os.path.exists(checkpoint_dir):
        print("[System] No checkpoints found for this project.")
        return
    checkpoints = [f.replace('.json', '') for f in os.listdir(checkpoint_dir) if f.endswith('.json') and not f.startswith('.')]
    if not checkpoints:
        print("[System] No checkpoints found for this project.")
        return
    print("[System] Available checkpoints:")
    for cp in checkpoints:
        print(f"  - {cp}")

# --- Helper Functions for Parsing State (REFACTORED) ---
def get_milestone_ids_from_plan(plan):
    """Extracts all milestone IDs from the plan, assuming a dictionary structure."""
    if not isinstance(plan, dict) or not isinstance(plan.get('milestones'), dict):
        return []
    return list(plan.get('milestones', {}).keys())

def get_task_ids_from_plan(plan):
    """Extracts all task IDs from the plan, assuming a dictionary structure."""
    task_ids = []
    if not isinstance(plan, dict) or not isinstance(plan.get('milestones'), dict):
        return []
    for m_content in plan.get('milestones', {}).values():
        if isinstance(m_content, dict) and isinstance(m_content.get('tasks'), dict):
            task_ids.extend(m_content.get('tasks', {}).keys())
    return task_ids

# --- .archyignore Functionality ---
def load_ignore_rules():
    """Loads rules from .archyignore file in the project directory."""
    ignore_file_path = os.path.join(project_path, ".archy", ".archyignore")
    if not os.path.exists(ignore_file_path):
        return []
    with open(ignore_file_path, 'r', encoding='utf-8') as f:
        # Return a list of non-empty, non-comment lines
        return [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

def is_ignored(file_path, ignore_rules):
    """Checks if a file path matches any of the ignore rules."""
    for pattern in ignore_rules:
        if fnmatch.fnmatch(file_path, pattern):
            return True
    return False

# --- Interactive Mode Functionality ---
def prompt_for_id(prompt_message, id_options):
    """Prompts the user to select an ID from a list of options."""
    if not id_options:
        print(f"[System] No options available for this command.")
        return None
    while True:
        try:
            choice_str = input(f"{prompt_message} (enter the number or press Enter to cancel): ")
            if not choice_str:
                print("[System] Canceled.")
                return None
            choice_index = int(choice_str) - 1
            if 0 <= choice_index < len(id_options):
                return id_options[choice_index]
            else:
                print("[System] Invalid number. Please try again.")
        except ValueError:
            print("[System] Invalid input. Please enter a number.")

# --- Dependency Management ---
def aggregate_dependencies(dependency_string):
    """Parses a dependency string and adds it to the aggregated list in the state."""
    if not dependency_string or not isinstance(dependency_string, str):
        return
    parts = dependency_string.strip().split()
    if not parts:
        return
    if parts[0] == 'pip' and parts[1] == 'install':
        deps_list = project_state['aggregatedDependencies'].setdefault('pip', [])
        new_deps = [dep for dep in parts[2:] if dep not in deps_list]
        if new_deps:
            deps_list.extend(new_deps)
            print(f"[System] Aggregated Pip dependencies: {', '.join(new_deps)}")
    elif parts[0] == 'npm' and parts[1] == 'install':
        deps_list = project_state['aggregatedDependencies'].setdefault('npm', [])
        # Simple parsing, ignores flags like -D or --save-dev for now
        new_deps = [dep for dep in parts[2:] if not dep.startswith('-') and dep not in deps_list]
        if new_deps:
            deps_list.extend(new_deps)
            print(f"[System] Aggregated NPM dependencies: {', '.join(new_deps)}")

def sync_dependency_files():
    """Writes the aggregated dependencies to their respective files."""
    os.makedirs(project_path, exist_ok=True)
    # For Pip
    pip_deps = project_state.get('aggregatedDependencies', {}).get('pip', [])
    if pip_deps:
        req_path = os.path.join(project_path, "requirements.txt")
        with open(req_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(sorted(pip_deps)))
        print(f"[System] Updated '{req_path}' with aggregated dependencies.")
    # For NPM
    npm_deps = project_state.get('aggregatedDependencies', {}).get('npm', [])
    if npm_deps:
        pkg_path = os.path.join(project_path, "package.json")
        if os.path.exists(pkg_path):
            try:
                with open(pkg_path, 'r+', encoding='utf-8') as f:
                    pkg_json = json.load(f)
                    pkg_json.setdefault('dependencies', {})
                    for dep in npm_deps:
                        if dep not in pkg_json['dependencies']:
                            pkg_json['dependencies'][dep] = "latest"
                    f.seek(0)
                    json.dump(pkg_json, f, indent=2)
                    f.truncate()
                print(f"[System] Updated '{pkg_path}' with aggregated dependencies.")
            except (json.JSONDecodeError, IOError) as e:
                print(f"[System] Could not update package.json automatically: {e}")
        else:
            print(f"[System] Could not find 'package.json' to update. Please manage NPM dependencies manually.")

# --- LLM Interaction & State Processing ---
def generate_prompt_for_user(user_command):
    """Constructs a context-aware prompt, prints it, and copies it to the clipboard."""
    command_parts = user_command.split(maxsplit=1)
    command = command_parts[0].lower()
    args = command_parts[1] if len(command_parts) > 1 else ""
    if not args and command not in ['generate_readme']:
        print(f"[System] The '{command}' command requires arguments.")
        return None, {}
    context_state = {
        "plan": project_state.get("plan"),
        "projectConfig": project_state.get("projectConfig")
    }
    target_id = args.split()[0].upper() if args else ''
    milestone_id = target_id.split('-')[0]
    task_id = target_id if '-' in target_id else None
    if project_state.get("specifications", {}).get(milestone_id):
        context_state['specifications'] = {milestone_id: project_state["specifications"][milestone_id]}
    existing_files_prompt_section = ""
    file_ownership = {}
    if command == 'code' and task_id:
        print(f"[System] Analyzing task '{task_id}' for file overlaps...")
        # 1. Get all files planned for the current task from its specification
        planned_files = []
        try:
            # This logic handles the spec format: "specifications": { "M1": { "M1-T1": { ... } } }
            milestone_specs = project_state.get("specifications", {}).get(milestone_id, {})
            task_spec = milestone_specs.get(task_id)
            if task_spec:
                planned_files.extend(task_spec.get('file_structure', []))
        except Exception as e:
            print(f"[System] Warning: Could not read file structure from specification for {task_id}. {e}")
        if not planned_files:
             print(f"[System] No 'file_structure' found in spec for {task_id}. Proceeding with standard 'code' command.")
        # 2. Find the current owner of each planned file
        all_code = project_state.get('code', {})
        for planned_file_path in planned_files:
            for owner_id, code_block in all_code.items():
                if owner_id == task_id: continue
                if planned_file_path in code_block.get('files', {}):
                    file_ownership[planned_file_path] = owner_id
                    break
        # 3. Build the context for files that need modification
        files_to_modify = []
        if file_ownership:
            print("[System] Overlap detected! Building a smarter prompt to handle modifications.")
            for file_path, owner_id in file_ownership.items():
                owner_code = all_code.get(owner_id, {})
                content = owner_code.get('files', {}).get(file_path, '')
                files_to_modify.append({
                    "path": file_path,
                    "content": content,
                    "owner_id": owner_id
                })
        if files_to_modify:
            existing_files_prompt_section += "\n\n--- EXISTING_FILES_TO_MODIFY ---\n"
            existing_files_prompt_section += "You MUST intelligently merge the new requirements for the task below into the following existing file(s). Do NOT simply replace them.\n\n"
            for f in files_to_modify:
                existing_files_prompt_section += f"File Path: {f['path']} (Owned by {f['owner_id']})\n"
                existing_files_prompt_section += f"Existing Content:\n```\n{f['content']}\n```\n\n"
    
    # Also include existing code if refining the same task
    elif command == 'refine' and task_id and project_state.get("code", {}).get(task_id):
        context_state.setdefault('code', {})[task_id] = project_state["code"][task_id]
    elif command == 'generate_readme':
        # README command needs all specifications for a full overview
        context_state['specifications'] = project_state.get("specifications")

    prompt = f"""{SYSTEM_PROMPT}

--- Current Project State (Context) ---
{json.dumps(context_state, indent=2)}
{existing_files_prompt_section}
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
    return prompt, file_ownership

# REFACTOR: New function to handle state updates from the AI
def process_state_update(update_data, file_ownership):
    """Handles merging the AI's state update into the global project_state."""
    global project_state

    tasks_with_modified_files = set()

    # --- Automatic File Syncing and State Merging Logic ---
    if 'code' in update_data:
        current_task_id = list(update_data['code'].keys())[0]
        new_code_block = update_data['code'][current_task_id]

        # Aggregate dependencies before state merge
        aggregate_dependencies(new_code_block.get('dependencies'))

        # Segregate files and update state
        new_files_for_current_task = {}

        for file_path, file_content in new_code_block.get('files', {}).items():
            if file_path in file_ownership:
                # This file belongs to another task, merge it there
                owner_id = file_ownership[file_path]
                owner_task_code = project_state['code'].setdefault(owner_id, {'files': {}})
                owner_task_code['files'][file_path] = file_content # Direct update
                print(f"[System] Staging update for '{file_path}' in owner task '{owner_id}'.")
                tasks_with_modified_files.add(owner_id) # Track the owner
            else:
                # This is a new file for the current task
                new_files_for_current_task[file_path] = file_content
        
        # Update state for the current task with only its new files
        if new_files_for_current_task:
            current_task_code = project_state['code'].setdefault(current_task_id, {'files': {}})
            current_task_code['files'].update(new_files_for_current_task)
            if new_code_block.get('dependencies'):
                current_task_code['dependencies'] = new_code_block['dependencies']
            tasks_with_modified_files.add(current_task_id)

        # Remove the original code update to prevent deep_merge from overwriting our careful logic
        del update_data['code']
    
    # Now, merge the rest of the update data (plan, specs, projectConfig, etc.)
    deep_merge(update_data, project_state)

    # --- Save and Sync ---
    if tasks_with_modified_files:
        print("\n[System] The following tasks have new or modified code:")
        for task_id in sorted(list(tasks_with_modified_files)):
             print(f"  - {task_id}")

        choice = input("Do you want to review and save these files now? (y/N): ").lower()
        if choice == 'y':
            for task_id in sorted(list(tasks_with_modified_files)):
                save_files_from_update(project_state['code'][task_id], task_id)
    
    save_state()
    print(f"[System] Project state updated and saved.")

    # Offer to sync dependency files
    sync_dependency_files()
    if 'readme' in update_data:
        save_readme(update_data['readme'])


# --- File Operations (uses global project_path) ---
def save_files_from_update(code_update, task_id, force_save=False):
    """Saves generated files to disk, prompting the user unless forced."""
    if not code_update or not code_update.get('files'):
        print(f"[System] No file information found for task {task_id}.")
        return
    ignore_rules = load_ignore_rules()
    choice = 'y' if force_save else ''
    if not force_save:
        print(f"\n[System] Files for task '{task_id}' will be saved in '{os.path.abspath(project_path)}/':")
        # Loop for displaying files
        for file_path in code_update.get('files', {}).keys():
            full_path_for_display = os.path.join(project_path, file_path)
            print(f"  - {full_path_for_display}")
        if code_update.get('dependencies'):
            print(f"\nInstall dependencies with: `{code_update['dependencies']}`")
        choice = input(f"Do you want to save/overwrite these files? (y/N): ").lower()
    if choice == 'y':
        # Loop for saving files
        for file_path, file_content in code_update.get('files', {}).items():
             if isinstance(file_path, str) and isinstance(file_content, str):
                output_dir_abs = os.path.abspath(project_path)
                final_path_abs = os.path.abspath(os.path.join(output_dir_abs, file_path))
                if not final_path_abs.startswith(output_dir_abs):
                    print(f"[System] Security Warning: Skipping file with malicious path: {file_path}")
                    continue
                # Check if file is ignored
                if is_ignored(file_path, ignore_rules):
                    print(f"  Skipped {final_path_abs} (ignored by .archyignore)")
                    continue
                os.makedirs(os.path.dirname(final_path_abs), exist_ok=True)
                with open(final_path_abs, 'w', encoding='utf-8') as f:
                    f.write(file_content)
                print(f"  Saved {final_path_abs}")
        print(f"[System] Files for {task_id} saved.")
    else:
        print(f"[System] File save for task '{task_id}' skipped.")

def save_readme(content):
    """Saves the README.md file to the project path."""
    os.makedirs(project_path, exist_ok=True)
    readme_path = os.path.join(project_path, "README.md")
    ignore_rules = load_ignore_rules()
    if is_ignored("README.md", ignore_rules):
        print("[System] README.md is in .archyignore, save skipped.")
        return
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
    global project_state, project_path
    print("Welcome to Archy AI Developer Co-pilot.")

    # --- Project Selection at Startup ---
    selected_path = select_project_path()
    if not selected_path:
        print("Exiting Archy. Goodbye!")
        return
    
    project_path = selected_path
    project_state = load_state()
    # Ensure the outputPath in the state is consistent with the selected path (Also to avoid malicious behaviour)
    project_state.setdefault('projectConfig', {})['outputPath'] = project_path
    save_state()

    if len(project_state) > 4: # Heuristic for existing project
         print(f"[System] Resumed project from '{project_path}'")
    else:
        print("[System] Started a new project.")
        print("Type 'plan <your project idea>' to start.")
    print("Type 'help' for a list of commands, or 'exit' to quit.")
    
    while True:
        # --- COMMAND PARSING ---
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
- specify <Milestone-ID>     : Generates specifications for a milestone. (Interactive)
- code <Task-ID>             : Generates or merges code for a task. (Interactive)
- refine <ID> <instruction>  : Modifies a plan, spec, or code. (Interactive)
- generate_readme            : Creates a README.md from the project state.
- sync <Task-ID|all>         : Recreates files from the project state, skipping ignored files.
- show_plan                  : Displays the current project plan.
- show_spec <Milestone-ID>   : Displays the specification for a milestone. (Interactive)
- show_code <Task-ID>        : Displays the code for a task. (Interactive)

ENHANCED COMMANDS:
- set-config <key> <value>   : Sets a global project configuration value (e.g., 'projectName').
- show-config                : Displays the current project configuration settings.
- check                      : Validates the project state for inconsistencies.
- checkpoint <name>          : Saves the current project state as a named checkpoint.
- list-checkpoints           : Shows all saved checkpoints.
- revert <name>              : Reverts the project state to a named checkpoint.
- undo                       : Reverts the last state-changing operation.
- exit                       : Quits the application.

Note: Commands marked (Interactive) will prompt you for a selection if run without arguments.
An .archyignore file can be created in your project's .archy directory to protect files from `sync` and `code` commands.
            """)
            continue
        
        # --- Commands that don't need the LLM ---
        elif command == 'check':
            print("[System] Running pre-flight checks...")
            issues_found = 0
            plan = project_state.get('plan', {})
            specs = project_state.get('specifications', {})
            code = project_state.get('code', {})

            # 1. Check for missing outputPath
            if not project_state.get('projectConfig', {}).get('outputPath'):
                print("  - [WARNING] Project 'outputPath' is not set in the configuration.")
                issues_found += 1
            # 2. Check for milestones without tasks
            if plan:
                for mid, mcontent in plan.get('milestones', {}).items():
                    if not mcontent.get('tasks'):
                        print(f"  - [WARNING] Milestone '{mid}' has no tasks defined.")
                        issues_found += 1
            # 3. Check for specifications without code (handles dict-of-objects structure for specs)
            for mid, milestone_specs_dict in specs.items():
                if not isinstance(milestone_specs_dict, dict): continue
                for task_id in milestone_specs_dict.keys():
                    if task_id and task_id not in code:
                        print(f"  - [INFO] Task '{task_id}' has a specification but no code yet.")
            
            # FIX: Correct Data Structure Handling in `check` command
            # 4. Check for code without tests (basic heuristic)
            for task_id, task_code in code.items():
                files = list(task_code.get('files', {}).keys())
                py_files = [f for f in files if f.endswith('.py') and not f.startswith('test_')]
                test_files = [f for f in files if (f.startswith('test_') or f.startswith('tests/')) and f.endswith('.py')]
                if py_files and not test_files:
                    print(f"  - [WARNING] Task '{task_id}' contains Python files but no corresponding test files.")
                    issues_found += 1
            
            if issues_found == 0:
                print("[System] All checks passed. No issues found.")
            else:
                print(f"\n[System] Check complete. Found {issues_found} potential issue(s).")
            continue

        elif command == 'set-config':
            if len(args.split()) < 2:
                print("[System] Usage: set-config <key> <value>")
                continue
            key, value = args.split(maxsplit=1)
            project_state.setdefault('projectConfig', {})[key] = value
            save_state()
            print(f"[System] Config set: '{key}' = '{value}'")
            continue
        elif command == 'checkpoint':
            if not args:
                print("[System] Usage: checkpoint <name>")
                continue
            save_checkpoint(args)
            continue
        elif command == 'list-checkpoints':
            list_checkpoints()
            continue
        elif command == 'revert':
            if not args:
                print("[System] Usage: revert <name>")
                continue
            choice = input(f"Are you sure you want to revert to checkpoint '{args}'? This will overwrite your current state. (y/N): ").lower()
            if choice == 'y':
                revert_to_checkpoint(args)
            else:
                print("[System] Revert canceled.")
            continue
        elif command == 'undo':
            revert_to_checkpoint('.undo')
            continue
        elif command == 'show-config':
            pprint(project_state.get('projectConfig', "No project configuration has been set."))
            continue

        # --- COMMANDS MODIFIED FOR INTERACTIVE MODE ---
        if command in ['specify', 'code', 'refine', 'show_spec', 'show_code'] and not args:
            ### Initialize selected_id for each loop ###
            selected_id = None
            plan = project_state.get('plan', {})
            if not plan:
                print("[System] A project plan is required. Use 'plan <description>' to start.")
                continue

            if command in ['specify', 'show_spec']:
                print("\n[System] Select a milestone:")
                options = get_milestone_ids_from_plan(plan)
                for i, mid in enumerate(options, 1):
                    print(f"  {i}. {mid}")
                selected_id = prompt_for_id("Select the milestone number", options)
            elif command in ['code', 'show_code']:
                print("\n[System] Select a task:")
                options = get_task_ids_from_plan(plan)
                for i, tid in enumerate(options, 1):
                    print(f"  {i}. {tid}")
                selected_id = prompt_for_id("Select the task number", options)
            elif command == 'refine':
                milestone_ids = get_milestone_ids_from_plan(plan)
                task_ids = get_task_ids_from_plan(plan)
                options = milestone_ids + task_ids
                
                print("\n[System] Select an artifact to refine:")
                print("--- Milestones ---")
                for i, mid in enumerate(milestone_ids, 1):
                    print(f"  {i}. {mid}")
                print("--- Tasks ---")
                for i, tid in enumerate(task_ids, len(milestone_ids) + 1):
                    print(f"  {i}. {tid}")
                
                selected_id = prompt_for_id("Select the artifact number", options)

            if not selected_id:
                continue
            if command == 'refine':
                instruction = input("Enter the refinement instruction: ")
                if not instruction:
                    print("[System] Refinement requires an instruction. Canceled.")
                    continue
                args = f"{selected_id} {instruction}"
            else:
                args = selected_id

        # --- Non-LLM Display Commands ---
            # Reconstruct the user input for prompt generation
            user_input = f"{command} {args}"

        if command == 'show_plan':
            pprint(project_state.get('plan', "No plan found."))
            continue
        elif command == 'show_spec':
            pprint(project_state.get('specifications', {}).get(args.upper(), "Specification not found."))
            continue
        elif command == 'show_code':
            pprint(project_state.get('code', {}).get(args.upper(), "Code not found."))
            continue
        elif command == 'sync':
            if not args:
                print("[System] Usage: sync <Task-ID | all>")
                continue
            if args.lower() == 'all':
                if not project_state.get('code'):
                    print("[System] No code found in the project state to sync.")
                    continue
                choice = input("Overwrite all managed files with current state? (y/N): ").lower()
                if choice != 'y':
                    print("[System] Sync canceled.")
                    continue
                print("[System] Syncing all tasks...")
                for task_id, code_block in project_state.get('code', {}).items():
                    save_files_from_update(code_block, task_id, force_save=True)
                print("[System] All tasks synced.")
            else:
                task_id_upper = args.upper()
                code_block = project_state.get('code', {}).get(task_id_upper)
                if code_block:
                    save_files_from_update(code_block, task_id_upper, force_save=False)
                else:
                    print(f"[System] Code for task '{task_id_upper}' not found. Use `code {task_id_upper}` to generate it.")
            continue

        # Create an auto-undo checkpoint before the LLM call
        save_checkpoint('.undo')
        
        # --- Commands that require the LLM ---
        prompt, file_ownership = generate_prompt_for_user(user_input)
        if prompt is None:
            continue
        
        print("\n[System] Paste the LLM's JSON response below and press Enter (or Ctrl+D/Ctrl+Z+Enter to finish):")
        response_str = ""
        try:
            lines = []
            while True:
                lines.append(input())
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
            # REFACTOR: Call the dedicated function to process the update
            process_state_update(response_json['stateUpdate'], file_ownership)
        else:
            print("[System] The AI indicated the request could not be completed successfully. Project state was not changed.")

if __name__ == '__main__':
    main()
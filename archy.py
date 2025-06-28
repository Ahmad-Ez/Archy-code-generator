import json
import os
import pyperclip
from pprint import pprint
import shutil
import fnmatch
import importlib.util

# --- Global Configuration for Archy ---
ARCHY_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".archy", "config.json")
MAX_RECENT_PROJECTS = 10
ARCHETYPE_DIR = "archetypes" # Directory for project archetypes

# --- Project-Specific Configuration (Dynamically Determined) ---
STATE_FILE_NAME = "project_state.json"
CHECKPOINT_DIR_NAME = ".archy/checkpoints"
ARCHETYPE_CONFIG_FILE = ".archy/archetype.conf"

# --- Global State Variables (Initialized in main) ---
project_path = None
project_state = {}
current_archetype_module = None # Will hold the loaded module for the current project
custom_commands = {} # Will hold custom commands from the archetype
COMMAND_DEFINITIONS = {
    # AI-Aware Commands (Included in the prompt to the LLM)
    "plan": {
        "usage": "plan <description>",
        "desc": "Creates a new project plan.",
        "ai_aware": True
    },
    "specify": {
        "usage": "specify <Milestone-ID>",
        "desc": "Generates specifications for a milestone. (Interactive)",
        "ai_aware": True
    },
    "code": {
        "usage": "code <Task-ID>",
        "desc": "Generates or merges code for a task. (Interactive)",
        "ai_aware": True
    },
    "refine": {
        "usage": "refine <ID> <instruction>",
        "desc": "Modifies a plan, spec, or code. (Interactive)",
        "ai_aware": True
    },
    "generate_readme": {
        "usage": "generate_readme",
        "desc": "Creates a README.md from the project state.",
        "ai_aware": True
    },
    # Client-Side Only Commands (For user help, but not sent to the LLM)
    "sync": {
        "usage": "sync <Task-ID|all>",
        "desc": "Recreates files from project state, skipping ignored files.",
        "ai_aware": False
    },
    "show-plan": {
        "usage": "show-plan",
        "desc": "Displays the current project plan.",
        "ai_aware": False
    },
    "show-spec": {
        "usage": "show-spec <Milestone-ID>",
        "desc": "Displays the specification for a milestone. (Interactive)",
        "ai_aware": False
    },
    "show-code": {
        "usage": "show-code <Task-ID>",
        "desc": "Displays the code for a task. (Interactive)",
        "ai_aware": False
    },
    "show-deps": {
        "usage": "show-deps",
        "desc": "Displays a summary of all dependencies from manifest files.",
        "ai_aware": False
    },
    "set-config": {
        "usage": "set-config <key> <value>",
        "desc": "Sets a global project configuration value (e.g., 'projectName').",
        "ai_aware": False
    },
    "show-config": {
        "usage": "show-config",
        "desc": "Displays the current project configuration settings.",
        "ai_aware": False
    },
    "check": {
        "usage": "check",
        "desc": "Validates the project state for inconsistencies.",
        "ai_aware": False
    },
    "checkpoint": {
        "usage": "checkpoint <name>",
        "desc": "Saves the current project state as a named checkpoint.",
        "ai_aware": False
    },
    "list-checkpoints": {
        "usage": "list-checkpoints",
        "desc": "Shows all saved checkpoints.",
        "ai_aware": False
    },
    "revert": {
        "usage": "revert <name>",
        "desc": "Reverts the project state to a named checkpoint.",
        "ai_aware": False
    },
    "undo": {
        "usage": "undo",
        "desc": "Reverts the last state-changing operation.",
        "ai_aware": False
    },
    "exit": {
        "usage": "exit",
        "desc": "Quits the application.",
        "ai_aware": False
    }
}
# --- System Prompt for the AI ---
def get_archy_master_prompt():
    """Returns the master system prompt for the AI, with commands generated dynamically."""
    # Generate the user commands section from the single source of truth
    user_commands_prompt_section = "\n--- User Commands ---\nYou will respond to the following commands from the user. Client-side commands are listed for your awareness.\n"
    for cmd, details in COMMAND_DEFINITIONS.items():
        if details["ai_aware"]:
            # These are commands the AI needs to process directly
            user_commands_prompt_section += f"- `{details['usage']}`: {details['desc']}\n"
        else:
            # These are commands the AI just needs to be aware of as client-side
            user_commands_prompt_section += f"- (Client-side) `{details['usage']}`: {details['desc']}\n"

    # The main prompt template
    base_prompt = """
You are "Archy," an expert AI software architect and developer. Your sole purpose is to collaborate with a user to transform a project plan into a complete, production-ready codebase. You are methodical, precise, and security-conscious.

--- Core Principles ---
1.  **Stateful Interaction**: You operate on a `projectState` JSON object provided in the prompt. Your response MUST be a single JSON object containing a `stateUpdate` that will be merged back into the project state.
2.  **Global Configuration**: If a `projectConfig` object is provided, you must use the values within it (e.g., projectName, author) to inform your generated code, comments, and documentation.
3.  **Archetype Context**: The user may provide additional context or instructions from a project "archetype." This context is an extension of these core principles and provides specialized guidance for the current project type (e.g., web app, CLI tool). Pay close attention to it.
4.  **Structured Output**: ALL of your output must be a single, self-contained JSON object following the specified schema: `{ "status": "...", "message": "...", "stateUpdate": { ... } }`.
5.  **Dependencies**: To add dependencies, you MUST directly modify the content of the appropriate manifest file (e.g., `package.json`, `requirements.txt`) within the `files` object. DO NOT use a separate 'dependencies' key.

--- The Workflow: PLAN -> SPECIFY -> CODE -> REFINE ---
1.  **PLAN**: Analyze the user's request and output a `projectState.plan` object. This object MUST contain a `milestones` dictionary.
2.  **SPECIFY**: Detail a milestone's tasks, describing purpose, file structure, etc. This populates `projectState.specifications`.
3.  **CODE**: Generate code files for a single task. This populates `projectState.code`.
4.  **REFINE**: Apply user-provided instructions to modify an existing plan, spec, or code artifact.

--- Understanding the State ---
You may encounter various top-level keys in the project state, such as `schema` (for database models), `apiContract` (for API endpoints), or `dataAssets`. Use the information within these keys to inform your architectural decisions and code generation. For example, if a `schema` key exists, your generated API and database code should reflect it.

--- IMPORTANT: Handling Existing Files & Dependencies ---
If the prompt includes an `EXISTING_FILES_TO_MODIFY` section, your primary goal is to intelligently merge the new requirements into the existing code.
- **For standard code files**, incorporate new logic without removing existing functionality unless specifically told to.
- **For manifest files (`package.json`, `requirements.txt`, etc.)**, you MUST add new dependencies to the existing ones. DO NOT simply replace the file. For `package.json`, merge the dependency objects. For `requirements.txt`, append the new libraries.
- Ensure the final generated `content` for any file is a complete, syntactically correct version of the file.

--- Quality & Security Gates (NON-NEGOTIABLE) ---
When generating code:
- **File Object Schema**: The `files` key MUST be a JSON object. Each key is the full relative `path` (string), and its value is the entire file `content` (string).
- **JSON String Escaping**: When the `content` of a file is provided as a string value in the JSON response, all double quotes (`"`) within that file's content MUST be properly escaped with a backslash (e.g., `\"`). This is critical for the overall JSON response to be syntactically valid.
- **Security**: Never hardcode secrets. Use placeholders like `os.environ.get("API_KEY")` and state they must be managed via environment variables. All database queries MUST use parameterized statements. Sanitize all user-facing inputs.
- **Error Handling**: Include robust error handling (e.g., try-except blocks).
- **Readability**: Code must be well-commented with clear docstrings and adhere to style guides (e.g., PEP 8 for Python).
- **Testing**: For each functional code file, provide a corresponding test file covering at least one success and one failure/edge case. The test file should be included in the `files` object of the same response.
"""
    # Append the dynamically generated commands section to the base prompt
    return base_prompt + user_commands_prompt_section

# --- Global Archy Config Management ---
def load_archy_config():
    """Loads the main archy config file with recent projects."""
    if not os.path.exists(ARCHY_CONFIG_PATH):
        return {"recent_projects": []}
    try:
        with open(ARCHY_CONFIG_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"recent_projects": []}

def save_archy_config(config):
    """Saves the main archy config file."""
    os.makedirs(os.path.dirname(ARCHY_CONFIG_PATH), exist_ok=True)
    with open(ARCHY_CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

def update_recent_projects(selected_path):
    """Adds a project path to the top of the recent projects list."""
    config = load_archy_config()
    recent_projects = config.get("recent_projects", [])
    if selected_path in recent_projects:
        recent_projects.remove(selected_path)
    recent_projects.insert(0, selected_path)
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
        choice = input("\nEnter a number, a new project path, or 'exit': ")
        if choice.lower() == 'exit':
            return None
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(recent_projects):
                selected_path = recent_projects[choice_num - 1]
                break
            else:
                print("[System] Invalid number. Please try again.")
        except ValueError:
            selected_path = os.path.abspath(choice)
            break
    if os.path.exists(selected_path) and not os.path.isdir(selected_path):
        print(f"[System] Error: The path '{selected_path}' points to a file, not a directory.")
        return None
    elif not os.path.exists(selected_path):
        create = input(f"The directory '{selected_path}' does not exist. Create it? (y/N): ").lower()
        if create == 'y':
            os.makedirs(selected_path)
            print(f"[System] Created project directory: '{selected_path}'")
        else:
            print("[System] Project selection canceled.")
            return None
    update_recent_projects(selected_path)
    print(f"[System] Using project directory: '{selected_path}'")
    return selected_path

# --- Archetype/Plugin Management ---
def load_archetypes():
    """Scans the archetypes directory and dynamically loads valid archetype modules."""
    archetypes = {}
    if not os.path.isdir(ARCHETYPE_DIR):
        print(f"[System] Warning: Archetypes directory '{ARCHETYPE_DIR}' not found.")
        return archetypes
    for filename in os.listdir(ARCHETYPE_DIR):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = filename[:-3]
            try:
                spec = importlib.util.spec_from_file_location(module_name, os.path.join(ARCHETYPE_DIR, filename))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'get_initial_state'):
                    archetypes[module_name] = module
                    print(f"[System] Loaded archetype: '{module_name}'")
                else:
                    print(f"[System] Warning: Skipping '{filename}' as it lacks a 'get_initial_state' function.")
            except Exception as e:
                print(f"[System] Error loading archetype '{filename}': {e}")
    return archetypes

def select_or_load_archetype(available_archetypes):
    """Loads the archetype for the current project or prompts the user to select one."""
    global current_archetype_module, custom_commands
    archetype_conf_path = os.path.join(project_path, ARCHETYPE_CONFIG_FILE)
    if os.path.exists(archetype_conf_path):
        with open(archetype_conf_path, 'r') as f:
            archetype_name = f.read().strip()
        if archetype_name in available_archetypes:
            current_archetype_module = available_archetypes[archetype_name]
            print(f"[System] Resumed project with archetype: '{archetype_name}'")
            return True
        else:
            print(f"[System] Error: Saved archetype '{archetype_name}' not found. Please select a new one.")

    # --- New Project or Missing Archetype ---
    if not available_archetypes:
        print("[System] Error: No archetypes found. Cannot start a new project.")
        return False

    print("\n[Archy] Select a project archetype:")
    options = list(available_archetypes.keys())
    for i, name in enumerate(options, 1):
        print(f"  {i}. {name}")

    while True:
        try:
            choice_str = input("Enter the number for the archetype: ")
            choice_index = int(choice_str) - 1
            if 0 <= choice_index < len(options):
                chosen_name = options[choice_index]
                current_archetype_module = available_archetypes[chosen_name]
                os.makedirs(os.path.dirname(archetype_conf_path), exist_ok=True)
                with open(archetype_conf_path, 'w') as f:
                    f.write(chosen_name)
                print(f"[System] New project started with archetype: '{chosen_name}'")
                return True
            else:
                print("[System] Invalid number.")
        except (ValueError, IndexError):
            print("[System] Invalid input.")

# --- State Management ---
def load_state():
    """Loads the project state from the JSON file."""
    state_file_path = os.path.join(project_path, ".archy", STATE_FILE_NAME)
    if os.path.exists(state_file_path):
        try:
            with open(state_file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"[System] Warning: Could not parse '{state_file_path}'. Check for errors.")
            return None
    return {} # Return empty dict for new projects

def save_state():
    """Saves the project state to the JSON file."""
    state_file_path = os.path.join(project_path, ".archy", STATE_FILE_NAME)
    os.makedirs(os.path.dirname(state_file_path), exist_ok=True)
    with open(state_file_path, 'w') as f:
        json.dump(project_state, f, indent=2)

def deep_merge(source, destination):
    """Recursively merges source dict into destination dict."""
    for key, value in source.items():
        if isinstance(value, dict):
            node = destination.get(key, {})
            destination[key] = deep_merge(value, node)
        else:
            destination[key] = value
    return destination

# --- Checkpoint and Undo Functionality ---
def save_checkpoint(name):
    """Saves the current project state as a checkpoint."""
    state_file_path = os.path.join(project_path, ".archy", STATE_FILE_NAME)
    checkpoint_dir = os.path.join(project_path, CHECKPOINT_DIR_NAME)
    if not os.path.exists(state_file_path):
        return False
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = os.path.join(checkpoint_dir, f"{name}.json")
    try:
        shutil.copyfile(state_file_path, checkpoint_path)
        if name != ".undo":
             print(f"[System] Checkpoint '{name}' saved.")
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
        project_state = load_state()
        print(f"[System] Project state reverted to checkpoint '{name}'.")
        return True
    except Exception as e:
        print(f"[System] Error reverting to checkpoint '{name}': {e}")
        return False

def list_checkpoints():
    """Lists all available checkpoints for the current project."""
    checkpoint_dir = os.path.join(project_path, CHECKPOINT_DIR_NAME)
    if not os.path.isdir(checkpoint_dir):
        print("[System] No checkpoints found for this project.")
        return
    checkpoints = [f.replace('.json', '') for f in os.listdir(checkpoint_dir) if f.endswith('.json') and not f.startswith('.')]
    if not checkpoints:
        print("[System] No checkpoints found for this project.")
        return
    print("[System] Available checkpoints:")
    for cp in sorted(checkpoints):
        print(f"  - {cp}")

# --- Helper Functions for Parsing State ---
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
    """Loads rules from .archyignore file."""
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
        print("[System] No options available for this command.")
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

# --- LLM Interaction & State Processing ---
def generate_prompt_for_user(user_command):
    """Constructs a context-aware prompt based on the archetype and state, prints it, and copies it to the clipboard."""
    # Determine the base prompt (either from Archy core or archetype override)
    if getattr(current_archetype_module, 'PROMPT_OVERRIDE', False):
        try:
            base_prompt = current_archetype_module.get_master_prompt()
        except AttributeError:
            print("[System] Error: Archetype has PROMPT_OVERRIDE=True but no get_master_prompt() function.")
            return None, {}
    else:
        base_prompt = get_archy_master_prompt()
        # Append additions from the archetype if they exist
        if hasattr(current_archetype_module, 'get_prompt_additions'):
            base_prompt += "\n" + current_archetype_module.get_prompt_additions()

    # --- Context building (similar to original logic) ---
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
    
    # Logic to find files that might be modified
    if command == 'code' and task_id:
        print(f"[System] Analyzing task '{task_id}' for file overlaps...")
        # 1. Get all files planned for the current task from its specification
        planned_files = project_state.get("specifications", {}).get(milestone_id, {}).get(task_id, {}).get('file_structure', [])
        if planned_files:
            # 2. Find the current owner of each planned file
            all_code = project_state.get('code', {})
            for planned_file_path in planned_files:
                for owner_id, code_block in all_code.items():
                    if owner_id != task_id and planned_file_path in code_block.get('files', {}):
                        file_ownership[planned_file_path] = owner_id
                        break
        # 3. Build the context for files that need modification
        if file_ownership:
            files_to_modify_context = []
            for file_path, owner_id in file_ownership.items():
                content = all_code.get(owner_id, {}).get('files', {}).get(file_path, '')
                files_to_modify_context.append({
                    "path": file_path,
                    "content": content,
                    "owner_id": owner_id
                    })
            
            if files_to_modify_context:
                existing_files_prompt_section += "\n\n--- EXISTING_FILES_TO_MODIFY ---\n"
                existing_files_prompt_section += "You MUST intelligently merge the new requirements into the following existing file(s). For manifest files (package.json, requirements.txt), add new dependencies to the existing ones.\n\n"
                for f in files_to_modify_context:
                    existing_files_prompt_section += f"File Path: {f['path']} (Owned by {f['owner_id']})\n"
                    existing_files_prompt_section += f"Existing Content:\n```\n{f['content']}\n```\n\n"

    # Also include existing code if refining the same task
    elif command == 'refine' and task_id and project_state.get("code", {}).get(task_id):
        context_state.setdefault('code', {})[task_id] = project_state["code"][task_id]
    
    elif command == 'generate_readme':
        # README command needs all specifications for a full overview
        context_state['specifications'] = project_state.get("specifications")

    prompt = f"{base_prompt}\n\n--- Current Project State (Context) ---\n{json.dumps(context_state, indent=2)}\n\n--- User Command ---\n{user_command}"

    print("\n--- PROMPT FOR MANUAL EXECUTION (Copied to Clipboard) ---")
    print(prompt)
    print("-------------------------------------------------------------")
    try:
        pyperclip.copy(prompt)
        print("[System] Prompt has been copied to your clipboard.")
    except pyperclip.PyperclipException:
        print("[System] Could not copy to clipboard. Please install 'pyperclip' or copy the prompt manually.")
    return prompt, file_ownership

def _merge_requirements_txt(old_content, new_content):
    """Merges two requirements.txt file contents."""
    old_reqs = set(line.strip() for line in old_content.splitlines() if line.strip())
    new_reqs = set(line.strip() for line in new_content.splitlines() if line.strip())
    merged_reqs = sorted(list(old_reqs.union(new_reqs)))
    return "\n".join(merged_reqs) + "\n"

def _merge_package_json(old_content, new_content):
    """Merges two package.json file contents, prioritizing new values."""
    try:
        old_pkg = json.loads(old_content)
        new_pkg = json.loads(new_content)
        # Deep merge for dependencies and scripts
        for key in ['dependencies', 'devDependencies', 'scripts']:
            if key in new_pkg:
                if key not in old_pkg or not isinstance(old_pkg.get(key), dict):
                    old_pkg[key] = {}
                old_pkg[key].update(new_pkg[key])
        # Overwrite other top-level properties
        for key, value in new_pkg.items():
            if key not in ['dependencies', 'devDependencies', 'scripts']:
                old_pkg[key] = value
        return json.dumps(old_pkg, indent=2)
    except json.JSONDecodeError:
        print("[System] Warning: Could not parse package.json for merging. Using new content as-is.")
        return new_content

def process_state_update(update_data, file_ownership):
    """Handles merging the AI's state update into the global project_state."""
    global project_state

    # --- Pre-process to merge manifest files before deep_merge ---
    if 'code' in update_data:
        for task_id, code_block in update_data['code'].items():
            if 'files' not in code_block: 
                continue
            
            # Use a copy to avoid issues while iterating
            files_to_update = {} 
            for file_path, new_content in code_block['files'].items():
                # Determine the original owner of the file to get the 'old_content'
                owner_id = file_ownership.get(file_path, task_id)
                old_content = project_state.get('code', {}).get(owner_id, {}).get('files', {}).get(file_path)

                if old_content:
                    merged_content = None
                    if file_path.endswith('requirements.txt'):
                        merged_content = _merge_requirements_txt(old_content, new_content)
                        print(f"[System] Merged dependencies in '{file_path}'.")
                    elif file_path.endswith('package.json'):
                        merged_content = _merge_package_json(old_content, new_content)
                        print(f"[System] Merged dependencies and scripts in '{file_path}'.")
                    
                    if merged_content:
                        # Store merged content to be updated later
                        files_to_update[file_path] = merged_content
            
            # Apply the merged content back to the update_data's file object
            code_block['files'].update(files_to_update)

    # Now, perform the main deep merge with the pre-processed data
    deep_merge(update_data, project_state)
    save_state()
    print("[System] Project state updated and saved.")
    if 'readme' in update_data:
        save_readme(update_data['readme'])
    tasks_with_new_code = list(update_data.get('code', {}).keys())
    if tasks_with_new_code:
        print("\n[System] The following tasks have new or modified code:")
        for task_id in sorted(tasks_with_new_code):
            print(f"  - {task_id}")
        if input("Do you want to sync these files to disk now? (y/N): ").lower() == 'y':
            for task_id in sorted(tasks_with_new_code):
                sync_task_files(task_id)

# --- File Operations ---
def sync_task_files(task_id, force_save=False):
    """Saves generated files for a specific task to disk."""
    # This function remains largely the same as the original.
    code_block = project_state.get('code', {}).get(task_id)
    if not code_block or not code_block.get('files'):
        print(f"[System] No file information found for task {task_id}.")
        return

    ignore_rules = load_ignore_rules()
    
    if not force_save:
        print(f"\n[System] Files for task '{task_id}' will be saved in '{os.path.abspath(project_path)}/':")
        # Loop for displaying files
        for file_path in code_block.get('files', {}).keys():
            print(f"  - {file_path}")
        if not input("Do you want to save/overwrite these files? (y/N): ").lower() == 'y':
            print(f"[System] File save for task '{task_id}' skipped.")
            return
    # Loop for saving files
    print(f"Saving files for {task_id}...")
    for file_path, file_content in code_block.get('files', {}).items():
         if isinstance(file_path, str) and isinstance(file_content, str):
            output_dir_abs = os.path.abspath(project_path)
            final_path_abs = os.path.abspath(os.path.join(output_dir_abs, file_path))
            if not final_path_abs.startswith(output_dir_abs):
                print(f"[System] Security Warning: Skipping file with malicious path: {file_path}")
                continue
            if is_ignored(file_path, ignore_rules):
                print(f"  Skipped {final_path_abs} (ignored by .archyignore)")
                continue
            os.makedirs(os.path.dirname(final_path_abs), exist_ok=True)
            with open(final_path_abs, 'w', encoding='utf-8') as f:
                # Un-escape the quotes before writing to the file
                corrected_content = file_content.replace('\\"', '"')
                f.write(corrected_content)
            print(f"  Saved {final_path_abs}")
    print(f"[System] Files for {task_id} saved.")


def save_readme(content):
    """Saves the README.md file to the project path."""
    os.makedirs(project_path, exist_ok=True)
    readme_path = os.path.join(project_path, "README.md")
    ignore_rules = load_ignore_rules()
    if is_ignored("README.md", ignore_rules):
        print("[System] README.md is in .archyignore, save skipped.")
        return
    print("\n[System] A new README.md is available.")
    choice = input("Do you want to save/overwrite the README.md file? (y/N): ").lower()
    if choice == 'y':
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[System] Saved {readme_path}")
    else:
        print("[System] README.md save skipped.")

# --- NEW: Dependency Display Command ---
def show_dependencies():
    """Parses all known manifest files in the state and prints a summary."""
    print("[System] Aggregating dependencies from project state...")
    all_deps = {'pip': set(), 'npm': set()}
    all_code = project_state.get('code', {})

    for task_id, code_block in all_code.items():
        for file_path, content in code_block.get('files', {}).items():
            if file_path.endswith('requirements.txt'):
                reqs = set(line.strip() for line in content.splitlines() if line.strip())
                all_deps['pip'].update(reqs)
            elif file_path.endswith('package.json'):
                try:
                    pkg = json.loads(content)
                    npm_deps = set(pkg.get('dependencies', {}).keys())
                    npm_dev_deps = set(pkg.get('devDependencies', {}).keys())
                    all_deps['npm'].update(npm_deps)
                    all_deps['npm'].update(npm_dev_deps)
                except (json.JSONDecodeError, AttributeError):
                    print(f"[System] Warning: Could not parse '{file_path}' in task '{task_id}'.")
    
    if not any(all_deps.values()):
        print("[System] No dependencies found in the project state.")
        return

    if all_deps['pip']:
        print("\n--- Pip Dependencies (from requirements.txt) ---")
        for dep in sorted(list(all_deps['pip'])):
            print(f"  - {dep}")

    if all_deps['npm']:
        print("\n--- NPM Dependencies (from package.json) ---")
        for dep in sorted(list(all_deps['npm'])):
            print(f"  - {dep}")

# --- Main Application Loop ---
def main():
    """The main REPL for interacting with Archy."""
    global project_state, project_path, current_archetype_module, custom_commands
    print("Welcome to Archy AI Developer Co-pilot.")

    available_archetypes = load_archetypes()
    if not available_archetypes:
        print("[System] No archetypes found. Please create a python file in the 'archetypes' directory.")
        return

    # --- Project Selection at Startup ---
    selected_path = select_project_path()
    if not selected_path:
        print("Exiting Archy. Goodbye!")
        return

    project_path = selected_path
    project_state = load_state()
    if project_state is None: # Handle JSON parsing error from load_state
        print("Exiting due to corrupted state file.")
        return


    # --- Archetype Selection and Initialization ---
    is_new_project = not bool(project_state)
    if not select_or_load_archetype(available_archetypes):
        return # Exit if no archetype could be selected/loaded

    if is_new_project:
        project_state = current_archetype_module.get_initial_state()
        project_state.setdefault('projectConfig', {})['outputPath'] = project_path
        save_state()
        print("[System] New project state initialized from archetype.")
    
    # Load custom commands from the archetype
    if hasattr(current_archetype_module, 'get_custom_commands'):
        custom_commands = current_archetype_module.get_custom_commands()
        if custom_commands:
            print(f"[System] Loaded {len(custom_commands)} custom command(s) from archetype.")


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
            print("\nAvailable Commands:")
            # Define categories for better organization
            llm_commands = ['plan', 'specify', 'code', 'refine', 'generate_readme']
            local_commands = ['sync', 'show-plan', 'show-spec', 'show-code', 'show-deps']
            enhanced_commands = ['set-config', 'show-config', 'check', 'checkpoint', 'list-checkpoints', 'revert', 'undo', 'exit']

            # Print standard commands
            for cmd_name in llm_commands + local_commands:
                details = COMMAND_DEFINITIONS.get(cmd_name, {})
                usage = details.get('usage', cmd_name).ljust(28)
                desc = details.get('desc', 'No description available.')
                print(f"- {usage}: {desc}")

            print("\nENHANCED COMMANDS:")
            for cmd_name in enhanced_commands:
                details = COMMAND_DEFINITIONS.get(cmd_name, {})
                usage = details.get('usage', cmd_name).ljust(28)
                desc = details.get('desc', 'No description available.')
                print(f"- {usage}: {desc}")

            # Print custom commands from archetype, if they exist
            if custom_commands:
                print("\nARCHETYPE COMMANDS:")
                for cmd_name, handler in custom_commands.items():
                    # Format archetype commands similarly
                    usage = cmd_name.ljust(28)
                    doc = handler.__doc__ or "No description available."
                    print(f"- {usage}: {doc.strip()}")
            
            print("\nNote: Commands marked (Interactive) will prompt you for a selection if run without arguments.")
            print("An .archyignore file can be created in your project's .archy directory to protect files from `sync` and `code` commands.")
            continue

        # --- Custom Command Handling ---
        if command in custom_commands:
            print(f"[System] Executing custom command: {command}")
            try:
                # Custom commands are expected to modify the project_state in place
                # or return a new state to be merged.
                # For simplicity, we'll have them modify the global state and then we save it.
                custom_commands[command](project_state)
                save_state()
                print("[System] Custom command executed and state saved.")
            except Exception as e:
                print(f"[System] Error executing custom command '{command}': {e}")
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
                if not isinstance(milestone_specs_dict, dict): 
                    continue
                for task_id in milestone_specs_dict.keys():
                    if task_id and task_id not in code:
                        print(f"  - [INFO] Task '{task_id}' has a specification but no code yet.")
            
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
            if input(f"Are you sure you want to revert to checkpoint '{args}'? (y/N): ").lower() == 'y':
                revert_to_checkpoint(args)
            continue
        elif command == 'undo':
            revert_to_checkpoint('.undo')
            continue
        elif command == 'show-config':
            pprint(project_state.get('projectConfig', "No project configuration has been set."))
            continue

        # --- Interactive Mode Logic for LLM Commands ---
        if command in ['specify', 'code', 'refine', 'show-spec', 'show-code'] and not args:
            ### Initialize selected_id for each loop ###
            selected_id = None
            plan = project_state.get('plan', {})
            if not plan:
                print("[System] A project plan is required. Use 'plan <description>' to start.")
                continue

            if command in ['specify', 'show-spec']:
                options = get_milestone_ids_from_plan(plan)
                selected_id = prompt_for_id("Select the milestone number", options)
            elif command in ['code', 'show-code', 'refine']:
                options = get_task_ids_from_plan(plan)
                selected_id = prompt_for_id("Select the task number", options)

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

        if command == 'show-plan':
            pprint(project_state.get('plan', "No plan found."))
            continue
        elif command == 'show-spec':
            pprint(project_state.get('specifications', {}).get(args.upper(), "Specification not found."))
            continue
        elif command == 'show-code':
            pprint(project_state.get('code', {}).get(args.upper(), "Code not found."))
            continue
        elif command == 'show-deps':
            show_dependencies()
            continue
        elif command == 'sync':
            if not args:
                print("[System] Usage: sync <Task-ID | all>")
                continue
            if args.lower() == 'all':
                if not project_state.get('code'):
                    print("[System] No code found in the project state to sync.")
                    continue
                if input("Overwrite all managed files with current state? (y/N): ").lower() == 'y':
                    print("[System] Syncing all tasks...")
                    for task_id in project_state.get('code', {}).keys():
                        sync_task_files(task_id, force_save=True)
                    print("[System] All tasks synced.")
            else:
                code_block = project_state.get('code', {}).get(args.upper())
                if code_block:
                    sync_task_files(args.upper(), force_save=False)
                else:
                    print(f"[System] Code for task '{args.upper()}' not found.")
            continue

        # Create an auto-undo checkpoint before the LLM call
        save_checkpoint('.undo')
        prompt, file_ownership = generate_prompt_for_user(user_input)
        if prompt is None:
            continue

        print("\n[System] Paste the LLM's JSON response below (Ctrl+D (macOS/Linux) or Ctrl+Z then press Enter (windows) to finish):")
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
            response_str = response_str.replace('\u00a0', ' ')
            response_json = json.loads(response_str.strip())
        except json.JSONDecodeError:
            print("[System] Error: Invalid JSON response received. State not changed. Ensure you copy only the JSON object.")
            print("--- Received Text ---\n" + response_str + "\n-----------------------")
            continue

        print(f"\n[Archy] {response_json.get('message', 'No message received.')}")

        if response_json.get('status', '').lower() == 'success' and 'stateUpdate' in response_json:
            process_state_update(response_json['stateUpdate'], file_ownership)
        else:
            print("[System] The AI indicated the request could not be completed successfully. Project state was not changed.")


if __name__ == '__main__':
    main()
# Archy AI Developer Co-pilot

Archy is a local, command-line tool that acts as a "Prompt-Generation Co-pilot" for AI-assisted software development. It uses a structured, stateful workflow to help you guide a Large Language Model (LLM), like Google's Gemini, from a high-level idea to a complete, production-ready codebase.

This script manages the project's state, constructs perfectly-formatted, context-aware prompts, and provides a framework for saving and iterating on the code the LLM produces.

### Core Concepts

This tool is built on a few key principles to ensure a robust and predictable development process:

* **AI Persona ("Archy")**: The script generates prompts that instruct the LLM to act as an expert software architect, ensuring high-quality, consistent output.
* **Stateful and Local**: The entire project plan, specifications, and code are stored locally in a `project_state.json` file in your project's root. This allows you to pause and resume your work at any time.
* **Command-Driven Workflow**: You interact with Archy through a simple set of commands like `plan`, `code`, and `sync` to direct the development process.
* **Co-pilot Model**: The script does not require API keys. It generates prompts for you to manually use in your preferred LLM chat interface, and then you paste the response back into the tool.

### Features

* **Interactive REPL**: A simple command-line interface for managing your project.
* **Local State Persistence**: Automatically saves your progress to `project_state.json`.
* **Clean Project Scaffolding**: All generated code and files are placed into a dedicated `generated_project/` directory, keeping your workspace clean.
* **Clipboard Integration**: Automatically copies generated prompts to your clipboard (requires `pyperclip`).
* **File Syncing**: A `sync` command to regenerate the `generated_project/` directory from the state file, perfect for version control or moving a project.

### Project Structure

When you use the tool, your directory will be organized as follows:

```
your-project-folder/
│
├── generated_project/      <-- All your project's code, tests, and README go here.
│   ├── src/
│   │   └── main.py
│   └── README.md
│
├── archy.py                <-- The co-pilot script.
│
├── project_state.json      <-- The "brain" of your project. Safely commit this file.
│
└── README.md               <-- This file, explaining how to use the co-pilot.
```

### Requirements

* Python 3.x
* `pyperclip` (optional, for automatic prompt copying)
    ```sh
    pip install pyperclip
    ```

### How to Use

1.  **Start the Script**: Run `python archy.py` in your terminal. It will either resume your last session from `project_state.json` or start a new project.
2.  **Plan Your Project**: Begin by describing your idea.
    ```
    > plan a simple python cli that counts words in a file
    ```
3.  **The Co-pilot Loop**:
    * The script will generate a detailed prompt and copy it to your clipboard.
    * Paste this entire prompt into your LLM (e.g., Gemini).
    * The LLM will return a structured JSON response.
    * Copy the full JSON response from the LLM.
    * Paste it back into the waiting Archy terminal and finish by typing `END_OF_JSON` on a new line and pressing Enter.
4.  **Generate Code**: Once you have specified a milestone, ask Archy to code a task.
    ```
    > code M1-T1
    ```
5.  **Save Files**: After a `code` command, Archy will ask for confirmation before saving the generated files into the `generated_project/` directory.
6.  **Review and Sync**: Use `show_plan` or `show_code <Task-ID>` to review your state. If you clone your project to a new computer, you only need the `archy.py` and `project_state.json` files. Run `sync all` to completely regenerate the `generated_project/` directory.

### Available Commands

| Command | Parameters | Description |
| --- | --- | --- |
| `plan` | `<description>` | Creates a new project plan and initializes the project state. |
| `specify` | `<Milestone-ID>` | Generates the detailed technical specifications for all tasks in a given milestone. |
| `code` | `<Task-ID>` | Generates the code, tests, and dependency commands for a single task. |
| `refine` | `<ID> <instruction>` | Modifies an existing plan, specification, or code artifact based on new instructions. |
| `sync` | `<Task-ID \| all>` | Recreates files from the project state on disk inside the `generated_project/` directory. |
| `show_plan`| *(none)* | Displays the current project plan stored in the state. |
| `show_spec`| `<Milestone-ID>` | Displays the generated specifications for a given milestone. |
| `show_code`| `<Task-ID>` | Displays the generated code for a given task. |
| `help` | *(none)* | Displays a list of all available commands and their usage. |
| `exit` | *(none)* | Quits the application. |
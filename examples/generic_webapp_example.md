# Example: Starting a Web Application

This document shows how to start a more complex project using the `generic_webapp` archetype. This approach provides a pre-defined structure, saving time on initial setup.

The goal is to demonstrate how to use a structured archetype to quickly bootstrap a project's foundation.

### Step 0: Start Archy and Select the Web App Archetype

We start the script and provide a path for our new To-Do List application.

**You run the script:**

```sh
python archy.py
```

**You type a path for the new app:**

```
/path/to/my-todo-app
```

**Archy creates the directory and prompts for an archetype. This time, we choose `generic_webapp`.**

```
The directory '/path/to/my-todo-app' does not exist. Create it? (y/N): y
[System] Created project directory: '/path/to/my-todo-app'
[System] Using project directory: '/path/to/my-todo-app'

[Archy] Select a project archetype:
  1. generic_webapp
  2. pex_webapp
  3. simple
Enter the number for the archetype: 1
[System] New project started with archetype: 'generic_webapp'
Type 'help' for a list of commands, or 'exit' to quit.
```

### Step 1: Explore the Pre-defined Plan

Unlike the `simple` archetype, this one comes with a plan already loaded. We can inspect it immediately.

**You type:**

```
> show-plan
```

**Archy displays the plan that was loaded from the archetype:**

```
{'description': 'A high-level plan for building a standard web application.',
 'milestones': {'M1': {'description': 'Backend Foundation',
                       'tasks': {'M1-T1': 'Setup FastAPI project with directory '
                                          'structure.',
                                 'M1-T2': 'Define Pydantic models based on the '
                                          'database schema.',
                                 'M1-T3': 'Implement database connection and '
                                          'User model using an ORM.',
                                 'M1-T4': 'Create authentication endpoints '
                                          '(/register, /login) based on the '
                                          'API contract.'}},
                'M2': {'description': 'Frontend Foundation',
                       'tasks': {'M2-T1': 'Setup React project using Create '
                                          'React App.',
                                 'M2-T2': 'Implement basic routing.',
                                 'M2-T3': 'Create an API client service to '
                                          'communicate with the backend.',
                                 'M2-T4': 'Build Register and Login page '
                                          'components.'}}}}
```

*(We can also use `show-config` to see the pre-configured services and database settings.)*

### Step 2: Generate the Backend Foundation

There is no need to use the `plan` command. We can immediately start executing the existing plan. Let's ask Archy to create the backend directory structure.

**You type:**

```
> code M1-T1
```

**After the LLM round-trip and syncing, Archy creates the initial files:**

```
[System] The following tasks have new or modified code:
  - M1-T1
Do you want to sync these files to disk now? (y/N): y
Saving files for M1-T1...
  Saved /path/to/my-todo-app/backend/app/main.py
  Saved /path/to/my-todo-app/backend/app/api/__init__.py
  Saved /path/to/my-todo-app/backend/app/core/config.py
  Saved /path/to/my-todo-app/backend/requirements.txt
  Saved /path/to/my-todo-app/backend/.gitignore
[System] Files for M1-T1 saved.
```

### Step 3: Implement the Database Model

Next, let's generate the code for the database connection and the `User` model, which was defined in the archetype's initial `schema`.

**You type:**

```
> code M1-T3
```

**The AI now has the context of the existing files and will add new ones and modify others where necessary.**

```
[System] The following tasks have new or modified code:
  - M1-T3
Do you want to sync these files to disk now? (y/N): y
Saving files for M1-T3...
  Saved /path/to/my-todo-app/backend/app/db/session.py
  Saved /path/to/my-todo-app/backend/app/models/user.py
  Saved /path/to/my-todo-app/backend/app/main.py
[System] Files for M1-T3 saved.
```

### Final Result

After just a few commands, we have the foundation of a backend service with a directory structure, configuration, database session management, and a `User` ORM model, all based on the structured `generic_webapp` archetype. The project is now ready for more detailed feature development.
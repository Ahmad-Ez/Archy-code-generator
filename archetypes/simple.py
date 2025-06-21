# archetypes/simple.py

def get_initial_state():
    """
    Returns a minimal initial state for a general-purpose project.
    """
    return {
        "projectConfig": {
            "outputPath": None, # Populated by Archy's core engine
            "projectName": "New Simple Project",
            "author": "Archy User",
            "version": "0.1.0"
        },
        "plan": {
            "description": "A new project plan has not been defined yet. Use the 'plan' command to create one.",
            "milestones": {}
        },
        "state": {
            "currentMilestone": None,
            "completedTasks": [],
        }
    }

def get_prompt_additions():
    """
    Returns a string of additional context for a simple project.
    """
    return """
--- Simple Project Archetype Context ---
This is a general-purpose project with no pre-defined architecture. You should rely entirely on the user's 'plan' command to establish the project's goals, technologies, and structure. Be prepared to build anything from a simple command-line script to a data processing library based on their description.
"""

def get_custom_commands():
    """
    Returns a dictionary of custom slash-commands. Simple projects have none.
    """
    return {}
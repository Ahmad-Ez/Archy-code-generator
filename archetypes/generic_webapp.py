# archetypes/generic_webapp.py

def get_initial_state():
    """
    Returns the initial state for a generic full-stack web application.
    """
    return {
        "projectConfig": {
            "outputPath": None, # Populated by Archy's core engine
            "projectName": "New Web Application",
            "author": "Archy User",
            "version": "0.1.0",
            "services": {
                "frontend": {
                    "framework": "React", # User can change this to Vue, Next.js, etc.
                    "path": "frontend/"
                },
                "backend": {
                    "framework": "FastAPI", # User can change this to Django, Flask, etc.
                    "path": "backend/"
                }
            },
            "database": {
                "type": "PostgreSQL",
                "name": "webapp_db"
            }
        },
        "schema": {
            "description": "Defines the core database models for the application.",
            "models": {
                "User": {
                    "fields": {
                        "id": "UUID (Primary Key)",
                        "username": "String (Unique, Not Null)",
                        "email": "String (Unique, Not Null)",
                        "hashed_password": "String (Not Null)",
                        "created_at": "DateTime",
                        "is_active": "Boolean"
                    }
                }
            }
        },
        "apiContract": {
            "description": "Defines the RESTful API contract between the frontend and backend.",
            "endpoints": [
                {
                    "path": "/api/v1/auth/register",
                    "method": "POST",
                    "description": "Registers a new user.",
                    "requestBody": "{ username, email, password }",
                    "response": "{ id, username, email }"
                },
                {
                    "path": "/api/v1/auth/login",
                    "method": "POST",
                    "description": "Logs in a user and returns a JWT.",
                    "requestBody": "{ email, password }",
                    "response": "{ access_token }"
                }
            ]
        },
        "plan": {
            "description": "A high-level plan for building a standard web application.",
            "milestones": {
                "M1": {
                    "description": "Backend Foundation",
                    "tasks": {
                        "M1-T1": "Setup FastAPI project with directory structure.",
                        "M1-T2": "Define Pydantic models based on the database schema.",
                        "M1-T3": "Implement database connection and User model using an ORM.",
                        "M1-T4": "Create authentication endpoints (/register, /login) based on the API contract."
                    }
                },
                "M2": {
                    "description": "Frontend Foundation",
                    "tasks": {
                        "M2-T1": "Setup React project using Create React App.",
                        "M2-T2": "Implement basic routing.",
                        "M2-T3": "Create an API client service to communicate with the backend.",
                        "M2-T4": "Build Register and Login page components."
                    }
                }
            }
        },
        "state": {
            "currentMilestone": "M1",
            "completedTasks": []
        }
    }

def get_prompt_additions():
    """
    Returns a string of additional context for a generic web app project.
    """
    return """
--- Generic Web App Archetype Context ---
This project is a standard full-stack web application with a separate frontend and backend.
- The **backend** should be built following RESTful principles.
- Use the `schema` key to define ORM models for the database.
- Use the `apiContract` key to build the API endpoints, including request/response validation.
- The **frontend** is a client-side application that consumes the backend API. It should handle user interface, state management, and making HTTP requests.
- Pay close attention to security, especially regarding password hashing and JWT-based authentication.
"""

def get_custom_commands():
    """

    Returns a dictionary of custom slash-commands. The generic web app has none
    to remain broadly applicable.
    """
    return {}
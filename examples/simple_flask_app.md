# Example: Creating a Simple Flask App

This document walks through a brief session with the Archy Co-pilot to create a simple "Hello, World!" web application using Python and Flask.

The goal is to demonstrate the core `plan -> specify -> code` workflow and showcase new features like project management and dependency aggregation.

### Step 0: Start Archy and Select a Project

First, we start the script. It now prompts us to select a project or create a new one by providing a path. For this example, we'll provide a path to a new folder.

**You run the script:**
```sh
python archy.py
```

**Archy asks you to choose a project:**
```
[Archy] Select a project or provide a new path.
  1. /path/to/another-project
  ...

Enter a number, a new project path, or 'exit':
```

**You type a path for your new app (use an absolute path):**
```
/path/to/my-flask-app
```

**Archy creates the directory and confirms:**
```
[System] The directory '/path/to/my-flask-app' does not exist.
Do you want to create it? (y/N): y
[System] Created project directory: '/path/to/my-flask-app'
[System] Using project directory: '/path/to/my-flask-app'
[System] Started a new project.
Type 'plan <your project idea>' to start.
```

### Step 1: Plan the Project

Now, inside the running tool, we use the `plan` command to describe our goal.

**You type:**
```
> plan a simple flask app with a single endpoint that returns a json greeting
```

**Archy generates a prompt, you use it with your LLM, and paste back the response. The state is updated, and Archy confirms:**

`[Archy] Project plan created successfully. You can now specify a milestone, e.g., 'specify M1'.`

*(Your `/path/to/my-flask-app/.archy/project_state.json` now contains the plan).*

### Step 2: Specify the Milestone

Next, we follow the suggestion and ask Archy to specify the technical details for the first milestone.

**You type:**
```
> specify M1
```

**After the LLM round-trip, Archy responds:**

`[Archy] Specification for M1 generated. You can now generate code for a task, e.g., 'code M1-T1'.`

*(The `project_state.json` is updated with detailed specifications for the files and logic needed).*

### Step 3: Generate the Code

Now we ask Archy to generate the Python code and the corresponding test file.

**You type:**
```
> code M1-T1
```

**After the LLM round-trip, Archy aggregates the dependencies, provides the code, and asks for confirmation to save the files directly into your project directory.**

`[Archy] Code for M1-T1 generated.`
```
[System] Aggregated Pip dependencies: flask, pytest
[System] Files for task 'M1-T1' will be saved in '/path/to/my-flask-app/':
  - /path/to/my-flask-app/app.py
  - /path/to/my-flask-app/test_app.py

Install dependencies with: `pip install flask pytest`
Do you want to save/overwrite these files? (y/N):
```

**You type `y` and Archy saves the files and updates the dependencies file:**
```
y
  Saved /path/to/my-flask-app/app.py
  Saved /path/to/my-flask-app/test_app.py
[System] Files for M1-T1 saved.
[System] Updated '/path/to/my-flask-app/requirements.txt' with aggregated dependencies.
```

### Final Result

After this short session, your project directory now contains a fully functional, testable Flask application and a `requirements.txt` file.

**`app.py`:**
```python
# app.py
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def get_greeting():
    """
    Returns a simple JSON greeting.
    """
    try:
        return jsonify({'message': 'Hello, World!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
```

**`test_app.py`:**
```python
# test_app.py
import unittest
import json
from app import app

class GreetingAPITestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_greeting_endpoint_success(self):
        """Test the '/' endpoint for a successful response."""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data['message'], 'Hello, World!')

if __name__ == '__main__':
    unittest.main()
```

**`requirements.txt`:**
```
flask
pytest
```
# Example: Creating a Simple Flask App

This document walks through a brief session with the Archy Co-pilot to create a simple "Hello, World!" web application using Python and Flask.

The goal is to demonstrate the core `plan -> specify -> code` workflow.

### Step 1: Plan the Project

First, we start the script and use the `plan` command to describe our goal at a high level.

**You type:**
```
> plan a simple flask app with a single endpoint that returns a json greeting
```

**Archy generates a prompt, you use it with your LLM, and paste back the response. The state is updated, and Archy confirms:**

`[Archy] Project plan created successfully. Next, run \`specify M1\` to detail the first milestone.`

*(Your `project_state.json` now contains the plan).*

### Step 2: Specify the Milestone

Next, we follow Archy's suggestion and ask it to specify the technical details for the first milestone.

**You type:**
```
> specify M1
```

**After the LLM round-trip, Archy responds:**

`[Archy] Specification for M1 generated. Next, run \`code M1-T1\` to generate the application code.`

*(Your `project_state.json` is updated with detailed specifications for the files and logic needed).*

### Step 3: Generate the Code

Now we get to the core of the work. We ask Archy to generate the Python code and the corresponding test file for the main task.

**You type:**
```
> code M1-T1
```

**After the LLM round-trip, Archy provides the code and asks for confirmation to save:**

`[Archy] Code for M1-T1 generated. You can now save the files.`

```
[System] Files for task 'M1-T1' will be saved in 'generated_project/':
  - generated_project/app.py
  - generated_project/test_app.py

Install dependencies with: `pip install flask pytest`
Do you want to save/overwrite the files for 'M1-T1'? (y/N):
```

**You type:**
```
y
```

**Archy saves the files:**

```
  Saved generated_project/app.py
  Saved generated_project/test_app.py
[System] Files for M1-T1 saved.
```

### Final Result

After this short session, your `generated_project/` directory now contains a fully functional, testable Flask application.

**`generated_project/app.py`:**
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

**`generated_project/test_app.py`:**
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

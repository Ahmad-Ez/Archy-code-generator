# Example: Creating a Simple CLI Tool

This document walks through a session with Archy to create a simple command-line tool that counts words and lines in a file.

This example demonstrates the core `plan -> specify -> code -> refine` workflow using the `simple` archetype, which is ideal for starting a project from a blank slate.

### Step 0: Start Archy and Select Project/Archetype

First, we start the script. For this new project, we provide a new directory path.

**You run the script:**

```sh
python archy.py
```

**You type a path for your new CLI tool:**

```
/path/to/my-word-counter
```

**Archy creates the directory and then prompts you to choose an archetype:**

```
The directory '/path/to/my-word-counter' does not exist. Create it? (y/N): y
[System] Created project directory: '/path/to/my-word-counter'
[System] Using project directory: '/path/to/my-word-counter'

[Archy] Select a project archetype:
  1. generic_webapp
  2. pex_webapp
  3. simple
Enter the number for the archetype: 3
[System] New project started with archetype: 'simple'
Type 'help' for a list of commands, or 'exit' to quit.
```

*(We selected `3` for the `simple` archetype).*

### Step 1: Plan the Project

Now, we use the `plan` command to describe our goal.

**You type:**

```
> plan a simple python cli that takes a file path as an argument and prints the number of words in that file.
```

**After the LLM round-trip, Archy confirms:**
`[Archy] Project plan created successfully. You can now specify a milestone, e.g., 'specify M1'.`

### Step 2: Specify the Milestone

We follow the suggestion and ask Archy to generate the technical specifications.

**You type:**

```
> specify M1
```

**After the LLM round-trip, Archy responds:**
`[Archy] Specification for M1 generated. You can now generate code for a task, e.g., 'code M1-T1'.`

### Step 3: Generate the Code

Now we ask Archy to generate the Python code and its test file.

**You type:**

```
> code M1-T1
```

**After the LLM round-trip, you sync the files to disk:**

```
[System] The following tasks have new or modified code:
  - M1-T1
Do you want to sync these files to disk now? (y/N): y
Saving files for M1-T1...
  Saved /path/to/my-word-counter/main.py
  Saved /path/to/my-word-counter/test_main.py
[System] Files for M1-T1 saved.
```

### Step 4: Refine the Code

The tool works, but now we want to add a feature to count lines as well. We use the `refine` command.

**You type:**

```
> refine M1-T1 also add a feature to count the number of lines in the file and print it alongside the word count.
```

**After the LLM round-trip, Archy updates the state. The AI has modified the existing files to add the new logic. We sync the changes:**

```
[System] The following tasks have new or modified code:
  - M1-T1
Do you want to sync these files to disk now? (y/N): y
Saving files for M1-T1...
  Saved /path/to/my-word-counter/main.py
  Saved /path/to/my-word-counter/test_main.py
[System] Files for M1-T1 saved.
```

### Final Result

Your project directory now contains an enhanced CLI tool with tests.

**`main.py`:**

```python
# main.py
import sys

def count_stats(file_path):
    """Reads a file and returns its word and line count."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            word_count = len(content.split())
            line_count = len(content.splitlines())
            return word_count, line_count
    except FileNotFoundError:
        return None, None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python main.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    words, lines = count_stats(file_path)
    
    if words is not None:
        print(f"File: {file_path}")
        print(f"Word Count: {words}")
        print(f"Line Count: {lines}")
    else:
        print(f"Error: File not found at '{file_path}'")
        sys.exit(1)
```
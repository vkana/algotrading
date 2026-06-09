```markdown
# algotrading Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and coding conventions used in the `algotrading` Python codebase. The repository focuses on algorithmic trading strategies, with each script typically representing a distinct trading logic. You'll learn how to update individual strategy scripts, coordinate changes across multiple scripts, manage dependencies, and handle deployment scripts, all while adhering to the project's coding standards.

## Coding Conventions

- **File Naming:**  
  Files use `camelCase` (e.g., `avgTestAccount.py`, `blshlimit.py`).

- **Import Style:**  
  Relative imports are preferred.  
  _Example:_
  ```python
  from .constants import TRADE_LIMIT
  ```

- **Export Style:**  
  Named exports are used (explicitly exporting functions/classes).  
  _Example:_
  ```python
  def run_strategy():
      pass

  __all__ = ['run_strategy']
  ```

- **Commit Messages:**  
  Freeform, short and descriptive (average ~23 characters).  
  _Example:_  
  ```
  fix avg_testaccount bug
  ```

## Workflows

### Single Script Feature or Bugfix
**Trigger:** When you want to implement a new feature or fix a bug in a specific trading strategy script.  
**Command:** `/update-strategy-script`

1. Edit the relevant strategy script file (e.g., `blshlimit.py` or `avg_testaccount.py`).
2. Commit the changes with a descriptive message.
   _Example commit message:_  
   ```
   improve blshlimit entry logic
   ```

### Multi-Script Coordinated Update
**Trigger:** When you need to update shared logic, logging, or perform code cleanup across several scripts.  
**Command:** `/multi-script-update`

1. Edit multiple strategy script files (e.g., `avg_testaccount.py`, `blshlimit.py`).
2. Optionally update shared files (e.g., `constants.py`).
3. Commit all changes together.
   _Example commit message:_  
   ```
   refactor logging in all strategies
   ```

### Add or Update .gitignore
**Trigger:** When you want to add new ignore rules or initialize the `.gitignore` file.  
**Command:** `/update-gitignore`

1. Edit or create the `.gitignore` file.
2. Commit the changes.
   _Example:_  
   ```
   *.pyc
   __pycache__/
   ```

### Requirements Update
**Trigger:** When you need to add a new dependency or fix requirements.  
**Command:** `/update-requirements`

1. Edit or create `requirements.txt`.
2. Commit the changes.
   _Example:_  
   ```
   numpy>=1.19.0
   pandas>=1.1.0
   ```

### Add or Update Shell Scripts and Procfile
**Trigger:** When you want to add or modify deployment/startup scripts.  
**Command:** `/update-shell-scripts`

1. Edit or create `start.sh`, `stop.sh`, or `Procfile`.
2. Commit the changes.
   _Example `start.sh`:_
   ```bash
   #!/bin/bash
   python blshlimit.py
   ```

## Testing Patterns

- **Test File Pattern:**  
  Test files are named with the pattern `*.test.*` (e.g., `blshlimit.test.py`).
- **Framework:**  
  Testing framework is unknown; check test files for custom or standard Python test usage.
- **Example Test File Name:**  
  ```
  avg_testaccount.test.py
  ```

## Commands

| Command                | Purpose                                              |
|------------------------|-----------------------------------------------------|
| /update-strategy-script| Update or fix a single trading strategy script      |
| /multi-script-update   | Make coordinated changes across multiple scripts    |
| /update-gitignore      | Add or update `.gitignore` rules                    |
| /update-requirements   | Add or update dependencies in `requirements.txt`    |
| /update-shell-scripts  | Add or update deployment and process management scripts |

```
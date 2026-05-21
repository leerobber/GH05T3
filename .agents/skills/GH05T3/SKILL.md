```markdown
# GH05T3 Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill provides guidance on contributing to the GH05T3 Python codebase. It covers the project's coding conventions, commit patterns, and testing approaches. While no formal frameworks or automated workflows are detected, this document outlines best practices for file organization, import/export styles, and test structuring to ensure consistency and maintainability.

## Coding Conventions

### File Naming
- Use **snake_case** for all Python files.
  - **Example:**  
    ```python
    # Correct
    my_module.py

    # Incorrect
    MyModule.py
    myModule.py
    ```

### Import Style
- Use **relative imports** within the package.
  - **Example:**
    ```python
    # In foo/bar.py
    from . import utils
    from ..models import User
    ```

### Export Style
- Use **named exports** by explicitly listing public objects in `__all__`.
  - **Example:**
    ```python
    # In my_module.py
    __all__ = ['MyClass', 'my_function']

    class MyClass:
        pass

    def my_function():
        pass
    ```

### Commit Patterns
- Commit messages are of mixed types, commonly prefixed with `fix`.
- Average commit message length: ~75 characters.
  - **Example:**
    ```
    fix: correct typo in user authentication logic
    ```

## Workflows

_No formal workflows detected in the repository._

## Testing Patterns

- **Testing Framework:** Unknown (not detected).
- **Test File Pattern:** Test files are named with the `*.test.ts` pattern, suggesting some TypeScript-based testing exists, possibly for frontend or cross-language components.
  - **Example:**
    ```
    user_auth.test.ts
    ```

- **Note:** There is no evidence of Python-specific testing frameworks (e.g., pytest, unittest) in the analysis.

## Commands
| Command | Purpose |
|---------|---------|
| /fix    | Use when committing bug fixes or corrections |
| /test   | Run or locate tests (if applicable) |
```
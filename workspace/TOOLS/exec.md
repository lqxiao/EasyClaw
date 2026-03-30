---
name: exec
description: Execute shell commands in the local workspace.
metadata: { "openclaw": { "emoji": "🛠", "requires": { "config": [] } } }
---

# Exec Tool

## Overview

Use the `exec` tool to run shell commands. Prefer small, targeted commands and read before you write. The tool accepts a single `command` string.

## Inputs to collect

- `command` (shell command to execute)
- Working directory if it must differ from the default workspace

If the user is vague ("check logs"), ask which file, directory, or command they want to run.

## Actions

### List files in the workspace

```json
{
  "command": "ls"
}
```

### Search for a string in the repo

```json
{
  "command": "rg -n \"TODO\" -S ."
}
```

### Show a file

```json
{
  "command": "sed -n '1,120p' README.md"
}
```

### Run a script

```json
{
  "command": "python main.py"
}
```

## Notes

- Prefer `rg` for searching and `rg --files` for file lists.
- Avoid destructive commands unless explicitly requested (e.g., `rm`, `git reset --hard`).
- Keep output small by scoping paths and using `sed -n` for partial views.
- For tools that require network access or elevated permissions, request approval first.

## Ideas to try

- Inspect repo layout and key files before making changes.
- Search for references before editing or refactoring.
- Run a minimal command to verify assumptions.

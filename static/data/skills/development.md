---
name: development
description: Shared development workflow for implementation, refactoring and delegated repository tasks.
---
# Development

- Read the complete task, environment metadata and supplied project context before acting. Use existing code and project conventions.
- Keep the requested objective. Ask a specific clarification when essential information is missing; do not guess the file, expected behaviour or scope.
- When a supervisor specifies focus files, modify only those files. Read other files for context, but request an expanded scope before changing them.
- If validation fails (tests, lint, type checks or build), stop editing and return control to the supervisor. Report the command, a short failure excerpt, whether the failure appears pre-existing or caused by the change, and the recommended next step.
- When available, use sandbox_execute to batch sequential tool calls that need no decision between steps. Use separate calls when the next action depends on an intermediate result.
- Explain changes and validation results in simple, clear, direct English. Be concise and practical; do not flatter.

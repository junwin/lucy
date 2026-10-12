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
- Use the configured root names supplied in the current environment instructions. For file, patch, repository and command tools, pass external_root and omit location. Names are arbitrary and case-sensitive; do not invent aliases or infer special behaviour from their names.
- Keep path, repository root and command working_directory relative to the selected configured directory. Include account and namespace subdirectories explicitly when needed. Scripts and program arguments may contain absolute paths when the program requires them.
- For patch_apply, retain the same full root-relative path used to read the file. Supply a numbered unified diff with a/ and b/ header prefixes or prefix-free headers; do not use *** Begin Patch syntax. Validate with check_only=true, then apply the same patch with check_only=false. Correct the reported format, hunk or path mismatch instead of repeatedly shortening paths.
- Explain changes and validation results in simple, clear, direct English. Be concise and practical; do not flatter.


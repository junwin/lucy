Please look at the module name below: `src/<module name>`.

Analyse every `.py` file in the module and produce a thorough `.md` document. Go beyond surface-level listing — read the actual source, docstrings, and comments.

The output document **must** include all of the following sections (in order):

---

## YAML Front Matter
Include tags as a YAML list. Tags must include:
- The module name as a tag (e.g. `src_agent`)
- `lucyproject`
- All distinctive class/enum/constant names from the module (not generic stuff like `Dict`, `List` — be selective)

---

## 1. Summary
A paragraph or two explaining:
- What the module does (its single responsibility)
- Where it fits in the overall architecture
- What problem it solves

---

## 2. Architecture & Design
Explain:
- Key design patterns used (ABC/Protocol, dependency injection via `injector`, strategy, registry, etc.)
- How the classes relate to each other (inheritance, composition, protocol adherence)
- Any legacy/v2 split and why it exists
- Important design decisions evident from comments/docstrings

---

## 3. Key Classes
Table with columns: Class | Base/Parent | Purpose

---

## 4. Source Files
List every `.py` file in the module. Table with columns: File | Responsibility | Notable Exports
Include the `__init__.py` if present — say what it exports.

---

## 5. Dependencies
Separate into:
- **Standard library** (stdlib modules used)
- **Third-party packages** (pypi packages)
- **Internal modules** (other `src.*` modules this module imports)
- **Optional dependencies** (try/except guarded imports, or deps only needed for certain features)

---

## 6. Configuration / Settings
List any config keys read from `ConfigManager` (`self.config.get(...)`), env vars, or file paths. Table with columns: Key | Type | Default | What it controls. If none, state "None".

---

## 7. Exceptions
List all custom exception classes defined in this module. Table with columns: Exception | Base | When Raised. If none, state "None".

---

## 8. Module-Level Constants
List important constants defined at module level (e.g. default values, limits, sentinels). If none, state "None".

---

## 9. Methods (by class)
For **each class** that has methods, a separate sub-table.

Columns: Method | Type (instance/class/staticmethod) | Signature | Description

For the description, include:
- What the method does (2-3 sentences)
- Key parameters (name, type, purpose)
- Return value
- Important edge cases or error conditions
- Any side effects (logging, file I/O, network calls)

Be thorough — extract this from the actual source code, docstrings, and type hints.

---

## 10. Usage Examples
Where applicable, include 1-2 code snippets showing how the module's main class is constructed and used. For very simple data-only modules, this section can say "N/A — data model only."

---

## 11. Edge Cases & Gotchas
Important things to know:
- Error handling patterns (per-item robustness? fail-fast?)
- Legacy field mapping or backward compatibility
- Thread-safety concerns
- Known limitations
- Any tricky validation logic

---

## 12. Consumers
Which other modules or entry points call/import this module. Table with columns: Consumer | What it uses. If unknown from source inspection, say "Unknown — trace imports to confirm."

---

Save the document as a single `.md` file:
- external_root = repo_lucy
- path = docs/<module name>.md
Please look at the module name below: `src/<module name>`.

Analyse the `.py` files in the module and produce a **compact** reference `.md` document. Read the actual source, docstrings, and comments.

The output document **must** include the following sections (in order):

---

## YAML Front Matter
Include tags as a YAML list. Tags must include:
- The module name as a tag (e.g. `src_agent`)
- `lucyproject`
- All distinctive class/enum/constant names from the module (not generic stuff like `Dict`, `List` — be selective)

---

## 1. Summary
One paragraph explaining what the module does, where it fits, and what problem it solves.

---

## 2. Key Classes
Table with columns: Class | Base/Parent | Purpose

---

## 3. Source Files
Table with columns: File | Responsibility | Notable Exports
Include `__init__.py` if present.

---

## 4. Dependencies
Separate into:
- **Standard library**
- **Third-party packages**
- **Internal modules** (other `src.*` imports)

---

## 5. Methods (by class)
For each class with methods, a sub-table with columns: Method | Type (instance/class/staticmethod) | Signature | Description

For descriptions: what it does, key parameters, return value, side effects.

---

Be concise. This is a mini/compact doc — not the full 12-section version.

Save the document as a single `.md` file:
- external_root = repo_lucy
- path = docs/minidoc/<module name>.md

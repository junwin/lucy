# Configured tool roots

File, patch, repository and command tools select a directory using
`external_root`, an arbitrary case-sensitive name from the effective
`external_roots` configuration. Handler paths are relative to that directory.
The model-facing schemas no longer require or advertise `location`.

`ConfigManager` merges `config.json` with `config.local.json` recursively.
Local entries override matching root names and can add new names; unmodified
global entries remain. The resolver and prompt instructions both read this
effective mapping. Configuration reloads are reflected on the next prompt
build and subsequent tool calls.

For example, if a root named `lucy_data_files` points to `/srv/lucy-data`, a
file request can use:

```json
{
  "external_root": "lucy_data_files",
  "path": "data/accounts/john/notes.txt"
}
```

The resolver does not interpret the name or add namespace/account directories.
Consuming code and callers specify those subdirectories when needed. A root
named `sandbox` behaves exactly like any other configured alias.

`path`, repository `root`, and command `working_directory` retain their relative
path and containment rules. Command scripts and program arguments may contain
absolute paths required by the invoked program; choosing a working directory
does not confine all program access. Existing explicit legacy `location` calls
retain their compatibility behavior in galet-tools, including legacy sandbox
account scoping and internal storage consumers.

Agents allowed to use file/repository/command tools or lazy discovery receive
the current root names and paths in system instructions passed to the prompt
compiler. This section participates in normal prompt budgeting and explains
the current calling convention even if an installed account-level `filepaths`
skill contains old examples. Other agents receive no additional root section.

The bundled development skill documents the same convention and the patch
validation workflow. Updating that bundled file does not overwrite existing
account skills. After reviewing an account's stored development skill, it can
be updated with the existing installer:

```bash
python scripts/install_development_skill.py --account junwin --overwrite
```

This branch pins galet-tools PR #30's exact commit so the schemas and runtime
support named-root calls together. Release 0.1.26 contains the patch fix only.
After PR #30 is merged and released, replace the Git commit requirement with
that published version before deploying the coordinated update.

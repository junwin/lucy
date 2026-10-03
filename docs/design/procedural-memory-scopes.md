# Procedural memory storage and scope

Lucy constructs procedural memory through `src/procedural_memory_config.py`.
The prompt builder, context tool, and `/context/names` endpoint use the same
configuration. Galet-memory owns Markdown parsing, import resolution, and scope
precedence. No database migration is required.

The paired implementation temporarily pins `galet-memory[vec]` to the exact
Git commit in its PR. Installing Lucy requirements therefore needs Git access;
replace that pin with the released PyPI version after publishing galet-memory.

## Default locations

Paths are relative to `storage_root_path / storage_namespace`:

| Scope | Contexts | Skills |
| --- | --- | --- |
| Global | `contexts/<name>.md` | `skills/<name>.md` |
| Account | `contexts/<account>/<name>.md` | `skills/<account>/<name>.md` |

Existing account files stay in place. Named skills supplied by an agent and
skills imported by a context both search these locations. The account version
replaces a same-named global skill, including its tool requirements. Files are
not automatically loaded merely because they exist in a global directory.

An account context replaces the complete global context: body, imports, tag,
mandatory tools, and search namespaces. Empty account definitions also override
global definitions. Other accounts still see the shared version. Lookup never
searches another account's directory.

The context tool and UI list show the union of global and account names once
per name. Loading a global-only context works. Saving or changing its required
tools copies the shared definition into the account directory before editing,
preserving unchanged body and frontmatter. Shared files remain untouched.

## Configuration

`config.local.json` can override the `procedural_memory` block in `config.json`:

```json
{
  "procedural_memory": {
    "root": "/srv/lucy/procedural-data",
    "context_resolution": "most_specific",
    "layout": {
      "global_contexts": "contexts",
      "account_contexts": "contexts/{account}",
      "global_skills": "skills",
      "account_skills": "skills/{account}",
      "project_contexts": null,
      "project_skills": null
    }
  }
}
```

Omit `root` to use the normal storage base. Null disables a location. Templates
are relative to the root and support `{account}` and `{project}`. Invalid names
and paths escaping the root are rejected by galet-memory. Restart Lucy after
changing construction settings.

`context_resolution="merge"` opts into galet-memory's original additive context
behavior. Skills still override by scope. Scope-specific raw editing remains
account-local. Project locations can be configured for callers that pass
`project_name`; the current Lucy chat request does not select project scope.

SQLite paths for episodic/semantic/working memory are independent of this block.

# Built-in galet-tools composition (issue #258)

Lucy uses `galet-tools==0.1.34` and its supported built-in registrar. Startup
registers Lucy-owned adapters first, snapshots their names, then calls
`register_builtin_handlers` with `collision="preserve"`. The package owns the
manifest and constructor bindings: future package tools need no individual
imports, stubs or registrations in Lucy.

Existing Lucy classes and backend factories win name collisions. In particular,
Lucy's structured `execute_command` retains its existing name and behavior;
`execute_command2` is separately discoverable from the package. Episodic operation
tools now come directly from the package registrar rather than Lucy's own list.

`build_handler_services(config)` in `src/handlers/galet_adapters.py` supplies
Lucy's storage/external-root resolver, account sandbox resolver and command
security policy on handler creation. It does not open memory databases or read
credentials. Existing adapters retain their configured fallback backends.

`ToolExecutor` supplies a `HandlerServices.execution_context()` on each call:

| Key | Host service |
| --- | --- |
| `semantic_memory` | Prompt builder's semantic service |
| `procedural_memory` | Prompt builder's scoped context/skill service |
| `episodic_store` | Executor's existing episodic service |

These shared backends, plus the trusted execution account, reach newly added
generic handlers through the same call path used by Lucy tools. MCP uses this
executor as well. Services remain host-owned; discovery never opens, closes or
reconfigures a memory runtime. Missing backends produce the package's explicit
tool errors; missing path configuration produces the existing Lucy resolver
errors when used. Package optional-import skips are included in the startup
registration report. Unexpected registration failures propagate.

The paired discovery catalog labels preserved host names `lucy:` and added
package/extension names `galet-tools:`. Installed third-party registrars run
after built-in composition, retaining their sorted discovery and strict
collision checks. They cannot silently replace host or built-in registrations.

Registration does not change agent configuration. Both the existing
agent/context selection pipeline and MCP allowlists continue to apply. To use
a newly discoverable tool, grant it explicitly through the existing agent
`allowed_tools` configuration. A context can only narrow that permission.

For a new tool requiring a new constructor service, evolve the package's
`HandlerServices` contract and Lucy's service provider deliberately. Automatic
registration cannot supply a capability that the host does not have.

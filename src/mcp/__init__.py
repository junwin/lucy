"""MCP façade package: expose Lucy's HandlerRegistry to MCP clients.

Layout (see docs/design/mcp-handlerregistry.md):

- ``tool_adapter`` — pure translation of handler ``tool_def()``s into MCP tool
  schemas plus result/error mapping (``isError`` semantics). No I/O.
- ``server`` — transport + lifecycle (added in a later task): resolves the
  configured agent/account/context via the DI container, lists tools from the
  registry, dispatches calls through the existing ``ToolExecutor``.
"""

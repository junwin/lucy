# Runtime configuration reload

Send `POST /admin/reload` using the currently configured API key in the
`X-API-Key` header (or `Authorization: Bearer ...`). The normal API-key
configuration applies; configure authentication before exposing this endpoint.

The endpoint reads `config.json` and optional `config.local.json`, validates
the merged configuration, and validates every agent from the resulting
`agents_path`. It publishes changes only after both candidates pass. ConfigManager
and AgentManager instances remain shared, and the config dictionary retains its
identity. A changed agent path and strictness policy are retained for later reloads.

Successful responses return HTTP 200 with `config_reloaded`, `keys_added`,
`keys_removed`, `keys_changed`, `agents_loaded`, `agent_names`, `agents_added`,
and `agents_removed`. Logs contain key and agent names, not config values.
An API-key change applies to subsequent requests.

Missing required files, malformed JSON (including a present local override),
invalid structures, duplicate agent names, and invalid agent entries return
HTTP 500 with `config_reloaded: false`, `failed_stage`, `error`, and `detail`.
Both old managers' state remains intact. An absent local override is allowed;
an explicit empty agents list is a valid request to remove all agents.

`strict_agent_fields` defaults to `true` and must be a JSON boolean. Unknown
agent fields reject runtime reloads in strict mode; when `false`, they log
warnings and are ignored. Startup agent loading retains its existing tolerant
behavior of skipping individual invalid entries. The `agents_manage` reload
action also validates all entries and reports failures without removing live agents.

Reload requests are serialized within one process. Publication does not pause
in-flight chat requests, rebuild services created at startup (database stores,
provider clients, handlers holding copied settings, server host/port, etc.), or
update other worker processes. Restart for those changes. Agent changes apply
when a request next resolves an agent; an in-flight request can retain its existing
agent object.

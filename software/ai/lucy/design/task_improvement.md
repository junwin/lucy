Tasklist/domain validation and migration — Option A

Summary
- Keep domain objects as plain dataclasses (Task, TaskList).
- Add a strict validation boundary using Pydantic TypeAdapter for Task.from_dict / TaskList.from_dict when Pydantic is available.
- Configuration for the Pydantic models uses ConfigDict(extra='forbid') so unknown keys are rejected.

Schema (current, v2)
- Task
  - id: UUID string (Task constructor still accepts ints for legacy migration; ints normalized to deterministic UUID strings)
  - instructions: REQUIRED string (new name; legacy 'title' mapped)
  - state: string (kept from v1; default is TASK_STATE_PENDING)
  - result: optional dict|null
  - error: optional string|null
  - meta: dict (arbitrary callers' metadata)

- TaskList
  - schema_version: int = 2
  - id: string (required)
  - state: string
  - tasks: list[Task]
  - meta: dict
  - current_task_id: optional string (UUID)

Validation and serialization
- from_dict / from_json functions on Task and TaskList use Pydantic TypeAdapter when available to perform runtime validation and to ensure no extra fields are present.
- TypeAdapter is configured with ConfigDict(extra='forbid') so any unknown keys cause a validation error.
- to_dict / to_json produce the stable v2 shape.

Migration path from v1 -> v2
- Loader detects schema_version. If absent default to 2. Supported versions: 1 and 2.
- v1 differences handled:
  - Task.title -> instructions
  - Task.status -> state
  - numeric Task.id (int) -> converted to deterministic UUID string via UUIDv5(NAMESPACE_OID, str(int_id))
- Unknown task-level keys in v1 are rejected by default. If the caller explicitly passes allow_legacy_meta=True to TaskList.from_dict, unknown fields are moved into Task.meta (preserving the data) instead of raising.
- This behavior keeps migration explicit and avoids accidental acceptance of arbitrary payloads.

Developer notes / API changes
- Task.id is now always a string (UUID). Task.__init__ accepts ints (legacy) but normalizes to UUID string.
- Task.instructions is required (Task.title is accepted as legacy during deserialization/construction, but domain code should use instructions).
- TaskList.get_task signature updated to expect string IDs (UUID). Callers that previously passed integer ids must be updated to pass string ids (use TaskList.next_id() or convert ints using the deterministic UUID approach if needed).
- All serialization/deserialization goes through adapters and rejects unknown keys unless explicit migration allowance is provided.

Testing
- Unit tests should cover:
  - Unknown key rejection for Task.from_dict
  - Missing required fields raise errors
  - Migration behavior for v1 (title->instructions, int id conversion)
  - Unknown legacy keys moved into meta when allow_legacy_meta is True
  - Round-trip dump/load keeps schema_version 2 and preserves tasks/meta

Rationale
- Keeping domain objects lightweight dataclasses maintains simplicity for in-memory logic and easier mocking/stubbing.
- Using Pydantic as a boundary provides strict validation for external inputs without coupling the whole domain to Pydantic models.
- Explicit migration controls reduce risk when loading older, possibly untrusted data.

Implementation status
- The codebase in src/tasklists implements Option A: dataclasses with Pydantic TypeAdapter boundary, schema_version 2 for TaskList, Task.id as UUID-string, Task.instructions required, migration from v1 supported with allow_legacy_meta flag.
- Tests are included (tests/test_tasklists.py) exercising the validation and migration behavior.

Next steps / caveats
- Update any callers that relied on integer task ids to ensure they pass string ids.
- If Pydantic is not present in runtime, a fallback validation is used (weaker). Consider making Pydantic a runtime dependency for stronger guarantees in production.
- Ensure integration tests / endpoints are aligned with the new shapes (TaskList persisted JSON uses schema_version 2 and rejects unknown fields).
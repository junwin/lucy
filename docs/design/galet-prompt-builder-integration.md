# Galet prompt-builder integration

Lucy injects `PromptBuilderInterface` into `FunctionCallingProcessor`. The
processor does not select a concrete prompt implementation.

`PromptBuilderModule` keeps `CoALAPromptBuilder` as the default and selects
`GaletPromptBuilderAdapter` when this configuration flag is enabled:

```json
{
  "galet_prompt_builder_enabled": true
}
```

The adapter preserves Lucy's public `build_prompt(...)` contract. Lucy owns
agent resolution, application system instructions, attachment resolution, and
policy choice. `galet-prompt-builder` owns retrieval selection, section token
budgets, prompt assembly, and prompt metrics.

Policy is explicit and may be tuned independently of agent configuration:

```json
{
  "galet_prompt_builder": {
    "total_tokens": 8000,
    "safety_margin_tokens": 500,
    "procedural_tokens": 1500,
    "episodic_event_tokens": 1000,
    "episodic_digest_tokens": 500,
    "semantic_tokens": 1000,
    "maximum_events": 6,
    "maximum_digests": 2,
    "maximum_semantic_documents": 3,
    "semantic_score_threshold": 0.30,
    "digest_score_threshold": 0.40,
    "episodic_event_max_chars": 4000,
    "episodic_digest_max_chars": 1800,
    "semantic_item_max_chars": 1800
  }
}
```

`ConfigManager` deep-merges `config.local.json` over `config.json`, including
individual keys in `galet_prompt_builder`. The adapter reads that effective
section. Lucy's older global `prompt_budget_max_tokens` supplies `total_tokens`
only when the policy section does not specify it.

Lucy passes a plain `PromptPolicy` to galet-prompt-builder. Its defaults come
from that package; the `galet_prompt_builder` object in Lucy's effective config
overrides them. Legacy agent fields `max_prompt_conversations` and
`max_prompt_documents` supply limits only when those keys are absent from the
policy section; their dataclass defaults must not overwrite configured policy.
An agent's `prompt_budget_max_tokens`, when set, overrides `total_tokens`.
An agent can override any policy field using `prompt_policy`, applied last.
For example:

```json
{
  "name": "colin",
  "prompt_policy": {"procedural_tokens": 300, "semantic_score_threshold": 0.35}
}
```

The adapter translates Lucy's current CoALA memory contracts to the standalone
compiler. It also maps compiler metrics back to Lucy's existing prompt-token
breakdown so FCP prompt reports continue to work during migration.

This is a substitution boundary, not a dual prompt comparison framework. The
legacy implementation remains available as a rollback path while the Galet
selection and filtering policies are tuned.

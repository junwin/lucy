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

An agent's `prompt_budget_max_tokens`, `max_prompt_conversations`, and
`max_prompt_documents` override the corresponding global policy values. This
preserves existing per-agent safety caps while avoiding any dependency on an
agent object inside `galet-prompt-builder`.

The adapter translates Lucy's current CoALA memory contracts to the standalone
compiler. It also maps compiler metrics back to Lucy's existing prompt-token
breakdown so FCP prompt reports continue to work during migration.

This is a substitution boundary, not a dual prompt comparison framework. The
legacy implementation remains available as a rollback path while the Galet
selection and filtering policies are tuned.

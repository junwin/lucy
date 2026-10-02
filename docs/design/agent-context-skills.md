# Agent context and skills (Lucy #241, first implementation step)

Agent definitions accept `default_context`, `skills`, `skillset`, and
`prompt_policy`. `skills` are execution skill names; `skillset` advertises
capabilities for future routing. Both lists accept non-empty strings and are
normalized with stable deduplication. Existing definitions need no migration.

For every request, an explicit context takes precedence over `default_context`.
When neither supplies a context, agent skills can still load. The existing
`contextName: "none"` sentinel disables project context while retaining agent
skills. Agent changes affect subsequent messages; configuration is resolved
again for each prompt rather than copied from historical session metadata.

The skill order is agent skills first, followed by effective-context imports,
with each name appearing once. galet-memory owns scoped file lookup, missing
skill reporting, and skill content. galet-prompt-builder owns budgeting and
rendering; Lucy passes names without reading or concatenating skill files.
Agent prompt-policy overrides continue to take precedence over global settings.
Skill-required tools use the existing tool permission and registry validation.
Skills never grant additional tool permissions.

Example agent fields (merge with the normal model/tool configuration):

```json
{
  "name": "lumia",
  "default_context": "image_tool",
  "skills": ["image-cli", "filepaths", "dev-basics", "imagemagick", "gh-cli"],
  "skillset": ["image-processing", "image-creation"],
  "prompt_policy": {"procedural_tokens": 2000}
}
```

This step requires the companion named-skills branches in galet-memory and
galet-prompt-builder. The branch requirements pin their exact commits until
version 0.1.16 of both packages is reviewed and published; switch back to PyPI
pins at release time. No PyPI publication is performed by this change.

The production `FileProceduralMemory` implementation supports named skills.
The legacy context-repository-only adapter has no standalone skill repository
and rejects named-skill requests rather than silently ignoring them.

Next steps in #241: remove context selection in gptChum; integrate capability
publication and specialist selection with #143. LLM-capability routing remains
a possible future extension.

## Shared development instructions for Star and Colin

Star and Colin keep short identity/role prompts and load the shared `development`
skill before `filepaths` and `loop-prevention`. Its canonical source is
`static/data/skills/development.md`. Scope restrictions, clarification,
validation hard-stop, optional tool batching and writing style live there.
Models, tools, context, routing capabilities and prompt budgets are unchanged.

Skill storage is separate from the code checkout. Before using the slimmer
agent definitions, install the skill for each account that uses these agents:

```bash
python scripts/install_development_skill.py --account junwin
# Multiple accounts, if needed:
python scripts/install_development_skill.py --account junwin --account arla
```

The installer reads `config.json` plus `config.local.json`, uses the configured
storage root/namespace, and writes through galet-memory's account skill
repository. Identical installed content is left alone. A customised existing
`development` skill is preserved; review it before deliberately using
`--overwrite`. Reload agent configuration or restart Lucy after installation.
Skills still load through galet-memory and are budgeted by galet-prompt-builder;
no skill text is concatenated into agent system prompts.

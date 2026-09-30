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

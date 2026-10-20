# Message processor components (#279)

## Responsibility and dependency map

| Component | Responsibility | Dependencies and boundary |
| --- | --- | --- |
| `automation_processor.py` | Command parsing, tasklist lookup, ordered execution, checkpointing, task/list states, mandatory stops, execution records and episodic reporting | Injected storage, agent manager, episodic store, processor factory; calls the two components below. Remains the run coordinator. |
| `automation_inputs.py` | Assemble general instructions, task instructions, remaining metadata and attachment arguments | Receives TaskList and Task explicitly. No storage, factory, models or processor import. Consumes attachment fields from task metadata using the existing semantics. |
| `automation_agents.py` | Resolve run worker override, per-task agent and effective context | AgentManager supplied explicitly for each resolution; Task and Agent inputs. No execution or persistence. |
| `function_calling_processor.py` | Prompt/tool preparation, ordinary and streaming run setup, presentation and finalization | Existing ToolSelectionPipeline, ToolExecutor, LLMLoopRunner, EpisodicRecorder and metrics collaborators. Unchanged in PR 1. |
| `fcp_loop.py` | Model/tool iteration and continuation, iteration accounting, termination and output checks | Adapter, ToolExecutor, ProcessorContext, SSE events and metrics. Unchanged in PR 1. |

The two new modules never import AutomationProcessor. Their model/manager imports
are for type checking only. The processor constructor, public processing methods,
factory lookup and `_resolve_task_agent` compatibility method retain their
signatures. The wrapper uses the processor's current agent manager, rather than
capturing a copy at construction. Selection logs now originate in
`automation_agents`; message text and selection order are retained.

## Behaviour retained in PR 1

- Run worker override resolves before storage access. It wins over task agents.
- Otherwise: explicit task agent, caller's supplied secondary agent, configured
  partner, then caller. Unknown explicit agents fail; unavailable partners fall
  back to the caller. The explicit task agent matching the caller uses the
  caller object without a manager lookup.
- Context: nonempty run override (verbatim), stripped task context, stripped
  resolved-agent default, then empty string.
- Input order: stripped general instructions, stripped task instructions, then
  remaining metadata in insertion order as `name = value`.
- `meta.files` lists, including empty lists, beat singular `meta.file`.
  Attachment IDs are stringified. `meta.image_ids` accepts lists. Attachment
  keys are popped from nonempty metadata dictionaries, including invalid values,
  before remaining metadata becomes text. `Task.files` is not used by this path.
  Changing metadata consumption or attachment-only task policy is separate work.
- Assembly stays inside the per-task error handler, after the RUNNING checkpoint,
  and only when an FCP is available. Empty input still produces the existing
  completion warning; absent FCP still produces the existing placeholder result.
- The coordinator retains worker invocation, task state changes, persistence,
  records, mandatory stops, single/multi-step control and episodic events.

## Bounded PR sequence

1. **This PR:** automation inputs and agent/context selection, characterization
   coverage, dependency map and measurements.
2. **Next:** individual task execution/result interpretation and record/report
   construction. Keep checkpoint ordering and stop policies explicit in the
   coordinator; characterize failure paths before moving them.
3. **Then:** FCP prompt/tool preparation and shared run lifecycle/metrics. Reuse
   existing collaborators and preserve ordinary/streaming persistence and SSE
   ordering rather than forcing both interfaces into one presentation path.
4. **Finally:** reassess remaining `fcp_loop.run()` responsibilities with the
   smaller coordinators. Keep iteration state and semantics understandable
   together; avoid a split justified solely by file size.

PR 1 advances #279; it does not complete or close it.

## Source measurements

Measured from develop `069d4c2e3c0390feef99891063f9e7f4cf52c99a` and PR 1.
Lines use `str.splitlines()`; characters use decoded Python source length.
Method spans include the signature through the final statement, excluding
decorators. These are source counts, not tokens or serialized tool responses.

| Module | Before lines / characters | After lines / characters |
| --- | ---: | ---: |
| automation_processor.py | 1,071 / 42,146 | 956 / 37,239 |
| automation_inputs.py | — | 64 / 2,209 |
| automation_agents.py | — | 138 / 4,731 |
| function_calling_processor.py | 1,015 / 39,972 | unchanged |
| fcp_loop.py | 425 / 18,591 | unchanged |

`execute_tasklist()` reduces from 539 to 486 lines. Total source increases due
to explicit interfaces and documentation; the gain is bounded reading scope.

| Representative focused change | Before | After PR 1 |
| --- | --- | --- |
| Input composition/attachment precedence | Locate block inside 539-line execute_tasklist in 1,071-line processor | 64-line input module; inspect the four-line call site for lifecycle placement and its focused integration tests |
| Agent/context selection | Resolver and inline worker/context blocks spread across the processor | 138-line selection module; coordinator retains the override branch and compatibility wrapper |
| Tool-size failure handling | Existing FCP/loop/executor path | Unchanged; no reduced-scope claim yet |
| Streaming output and persistence ordering | Existing FCP streaming path and collaborators | Unchanged; addressed in a later PR |

## Validation

New input characterization tests exercise the real coordinator with a recording
FCP and storage fake, without live models. They cover composition order,
attachment precedence/conversion, checkpoint snapshots of metadata consumption,
empty input, general-only input, absent FCP, failed RUNNING checkpoints and
multi-step execution exactly once per task. Existing task-agent tests exercise
the compatibility method and execution path for precedence and unknown agents.
Relevant automation, tasklist-run, identity, FCP, episodic SQLite and metrics
regressions are run alongside these tests.

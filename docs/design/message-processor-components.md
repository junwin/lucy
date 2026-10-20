# Message processor components (#279)

## Responsibility and dependency map

| Component | Responsibility | Dependencies and boundary |
| --- | --- | --- |
| `automation_processor.py` | Command parsing, tasklist lookup, ordered execution, checkpointing, task/list states, mandatory stops, execution records and episodic reporting | Injected storage, agent manager, episodic store, processor factory; calls the components below. Remains the run coordinator. |
| `automation_inputs.py` | Assemble general instructions, task instructions, remaining metadata and attachment arguments | Receives TaskList and Task explicitly. No storage, factory, models or processor import. Consumes attachment fields from task metadata using the existing semantics. |
| `automation_agents.py` | Resolve run worker override, per-task agent and effective context | AgentManager supplied explicitly for each resolution; Task and Agent inputs. No execution or persistence. |
| `automation_execution.py` | Attempt one worker invocation, interpret results/metrics, capture errors and mandatory-stop outcomes | Receives task/run arguments, clock, stop detector and warning list explicitly. Calls input assembly; no storage, task states, retries or loop. |
| `automation_records.py` | Construct versioned task execution records with optional result/error/metrics and parent/child identity | Receives task/tasklist, outcome fields, start time and clock. Generates record ID; does not persist. |
| `function_calling_processor.py` | Ordinary/streaming orchestration, persistence and SSE presentation, compatibility hooks | Supplies current collaborators to preparation and lifecycle helpers; retains loop calls and event order. |
| `fcp_prompt_preparation.py` | Prompt system-message assembly, attachment/image arguments, existing tool-pipeline invocation | Receives current config/registry/builder/adapter and hook callbacks; no processor import or retained state. |
| `fcp_prompt_metrics.py` | Prompt/token accounting and legacy metrics-endpoint eligibility/schema-budget helpers | Existing shared token estimator, cap resolver and eligibility filter; active selection still belongs to ToolSelectionPipeline. |
| `fcp_run_lifecycle.py` | Fresh per-run counters, correlation context/filter/handler, metrics-envelope construction and best-effort append | Shared singleton identities; receives the current handler/logger and clock; no presentation or model loop. |
| `fcp_loop.py` | Model/tool iteration and continuation, iteration accounting, termination and output checks | Adapter, ToolExecutor, ProcessorContext, SSE events and metrics. Unchanged in PR 1. |

The extracted modules never import AutomationProcessor. Their model/manager imports
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

1. **Merged in PR #291:** automation inputs and agent/context selection, characterization
   coverage, dependency map and measurements.
2. **Merged in PR #292:** individual task execution/result interpretation and execution-record
   construction. Checkpoint ordering, stop decisions and episodic reporting stay
   explicit in the coordinator. Add failure-path characterization for validation.
3. **PR 3:** FCP prompt/tool preparation and shared run lifecycle/metrics. Reuse
   existing collaborators and preserve ordinary/streaming persistence and SSE
   ordering rather than forcing both interfaces into one presentation path.
4. **Finally:** reassess remaining `fcp_loop.run()` responsibilities with the
   smaller coordinators. Keep iteration state and semantics understandable
   together; avoid a split justified solely by file size.

PRs 1–3 advance #279; they do not complete or close it.

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

## Stage 2: task execution and execution records

Based on develop `61ae1f9a37a45e24c4c8cdb21ddd7d465743f486`, which
contains merged PR #291.

`execute_task()` contains the previous single-task try/except block and returns
a TaskExecutionOutcome (result, error, metrics, error detail). It calls the worker
at most once. Input assembly and metadata consumption remain after the RUNNING
checkpoint and only when an FCP exists. Empty-message warnings and absent-FCP
placeholder results are unchanged. Result/metrics values already collected before
a mandatory stop remain available for the failed execution record.

The coordinator supplies its existing clock and mandatory-stop detector. The
mandatory-stop markers and detector remain there; MandatoryStopError is defined
in the execution component and re-exported from automation_processor to preserve
the existing import. Execution logs originate in automation_execution; generic
exception tracebacks now include that helper's frame. Message text is retained.

`build_task_execution_record()` retains the previous schema construction and
optional-field checks. It uses the tasklist's parent correlation plus the worker
child identity. A failed record append is still handled in the coordinator;
record construction does not turn an append attempt into a successful append.

Run control remains explicit in the coordinator in this order:

1. Select pending task, resolve agent/context, mark RUNNING and save checkpoint.
2. Derive child identity; attempt execution and interpret its outcome.
3. Attach task error and set the task state.
4. Construct and append the execution record.
5. Write the task episodic event and save the terminal task checkpoint.
6. Stop on failure or single-step; otherwise select the next pending task.
7. Final checkpoint and summary event on the existing non-early-return paths.

The existing completed-checkpoint failure behaviour is retained: the task may
remain Completed while the list becomes Failed, and later tasks do not execute.
No state-repair policy is introduced in this structural PR. Episodic payload and
summary construction stay together with their call order in the coordinator.

| Source | Stage 1 | Stage 2 |
| --- | ---: | ---: |
| automation_processor.py | 956 lines / 37,239 characters | 893 lines / 33,735 characters |
| execute_tasklist() span | 486 lines | 430 lines |
| automation_execution.py | — | 125 lines / 4,845 characters |
| automation_records.py | — | 54 lines / 1,855 characters |

Counts follow the convention above. Total source grows with explicit interfaces;
a result-interpretation change can now be read in the 125-line execution module
plus its coordinator call site, and a record-schema change in the 54-line record
module plus the append/error call site. Earlier input/agent modules, FCP
tool-size handling and streaming scope are unchanged.

### Stage 2 validation history

PR #292 was initially prepared without an execution environment, using static
extraction comparison only. On 2026-10-20 John reported that branch tests were
green, normal operations were OK and tasklists were working. PR #292 is now
merged into develop. This records user-reported dev-machine validation, not a
local test run by the assistant.

New `test_automation_execution_boundary.py` cases use a recording worker and a
timeline storage fake. They check single/multi-step checkpoint → call → record →
event order; lineage and optional fields; worker/metrics exceptions and mandatory
stops; append failure; and post-execution checkpoint failure without duplicate
execution. They are intended to run unchanged against stage 1 as characterization
as well as stage 2, but that baseline run is also pending.

Run the previous relevant regression group plus the new cases:

```bash
python -m pytest tests/test_automation*.py tests/test_task_agent_resolution.py tests/test_tasklists_run_handler.py tests/test_tasklist_runs.py tests/test_execution_identity.py tests/test_function_calling_processor.py tests/test_fcp_chat2_sqlite.py tests/test_fcp_models.py tests/test_run_metrics.py tests/test_run_metrics_logger.py
```

The 145 passing tests reported for PR 1 apply only to that earlier change.

## Stage 3: FCP preparation and shared run lifecycle

Base: develop `035e2fb8f80488d3c824685156cbed6ef3b1efd1`, after merged
PR #292. This is a structural extraction; prompt contents, selection policy,
budgets, model/tool calls, metrics values and SSE/persistence policy are retained.

### Preparation boundary

`fcp_prompt_preparation.py` owns environment-message assembly, attachment-reuse
and discovery guidance, provider prompt blocks, prompt-builder arguments and
ToolSelectionPipeline invocation. Image support is still checked before the
environment hook; the prompt is built before tool selection, then tokens are
measured. The existing 6,000-character builder argument is unchanged.

The processor's environment, tool-resolution and preparation methods remain
compatibility hooks with their original signatures. Each call supplies current
dependencies and bound hooks; no stale builder/config/registry references are
captured at construction. The processor passes its current ToolSelectionPipeline
symbol as the factory, retaining the existing test patch point.

`fcp_prompt_metrics.py` contains the unchanged token-breakdown and schema-budget
helpers. The metrics endpoint can still import resolve_tool_defs and
apply_handler_schema_budget through function_calling_processor. Their legacy
tail-trimming behaviour is distinct from active ToolSelectionPipeline budget
errors; no competing selector is introduced.

### Lifecycle boundary

`fcp_run_lifecycle.py` owns correlation counting, initial metrics, UTC envelope
timestamps, metrics-log path resolution, RunMetrics construction and finalization.
Both presentation methods call begin_run at the original initialization point,
receiving a fresh metrics dictionary and correlation token.

The correlation ContextVar, filter class and default handler are each defined
once and imported back into the processor as compatibility aliases. Context
restoration uses the same ContextVar that the logging filter reads. Constructor
and injection signatures, FCPResult and ToolHandlerError imports remain stable.
The existing _finalize_run hook delegates with the processor's current logger
and handler.

The ordinary and streaming methods retain their distinct cleanup sites.
No context-manager or unified response path is introduced:

- Ordinary success/error branches finalize at their original locations; the
  ordinary finally block still only logs a summary.
- Streaming still initializes lazily when iterated. Its main finally block
  finalizes after iteration completes or a yielded stream is closed.
- Early validation SSE paths still yield error, metrics, done before finalizing
  when iteration resumes. This extraction does not alter early-return generator
  cancellation semantics.
- Streaming still persists the user message before model work, and deliverable
  events before yielding. Ordinary response persistence still occurs after the
  model loop. Image deduplication, byte expansion and provider continuation are
  unchanged.
- Finalization still ends counting, resets correlation context, builds metrics,
  and attempts the best-effort metrics append in that order. Append failures
  remain logged without failing an otherwise completed response.

### Reading scope and source measurements

Counts use the same source-line/character convention as earlier stages.

| Module | Before | Stage 3 |
| --- | ---: | ---: |
| function_calling_processor.py | 1,015 lines / 39,972 characters | 651 lines / 25,635 characters |
| fcp_prompt_preparation.py | — | 166 lines / 6,234 characters |
| fcp_prompt_metrics.py | — | 157 lines / 6,120 characters |
| fcp_run_lifecycle.py | — | 190 lines / 6,134 characters |
| process_message() span | 214 lines | 197 lines |
| process_message_streaming() span | 231 lines | 214 lines |
| fcp_loop.py | 425 lines / 18,591 characters | unchanged |

Total source grows with explicit interfaces and compatibility hooks. Focused
reading is reduced without claiming token savings from the number of files:

| Focused change | Stage 3 reading scope |
| --- | --- |
| Prompt/system-message/image/tool argument composition | 166-line preparation module plus the thin preparation hook; selection internals still live in the existing pipeline |
| Token reporting or metrics-endpoint schema trimming | 157-line prompt metrics module and the existing cap/eligibility helpers |
| Correlation counting, metrics envelope or log append | 190-line lifecycle module plus the finalization hook/call sites when investigating timing |
| Streaming output order | 214-line streaming method in a 651-line coordinator; inspect lifecycle only for cleanup/identity concerns |
| Oversized tool-output failures | Loop/executor limits and outcome flow are unchanged; no reduced reading-scope claim for those internals |

### Stage 3 validation status

The session preparing stage 3 has no usable execution environment. **Python
syntax checks and pytest are pending.** The draft PR is prepared for dev-machine
validation.

Static comparison verifies that both public presentation-method bodies match the
base exactly after expanding the shared initialization call, that copied
token-accounting/correlation/metrics helpers retain their source, and that moved
preparation and finalization bodies match after explicit dependency renaming.
These checks do not replace Python execution or establish runtime correctness.

`tests/test_fcp_component_boundaries.py` adds 21 model-free characterization
cases through the existing processor hooks: current-dependency and patch-point
visibility, preparation/argument order and fresh system-message lists, lifecycle
and persistence/delivery order, correlation restoration and warning counts,
stream closure, preparation errors, best-effort metrics append errors and early
validation timing. They are designed to also run on the stage-two base, but
baseline execution is pending as well.

Run the existing regression groups plus the new boundary cases:

```bash
python -m pytest tests/test_fcp_component_boundaries.py tests/test_function_calling_processor.py tests/test_fcp_chat2_sqlite.py tests/test_fcp_models.py tests/test_allowed_tools.py tests/test_agent_caps.py tests/test_prompt_builder_metrics_endpoints.py tests/test_tool_selection*.py tests/test_run_metrics.py tests/test_run_metrics_logger.py tests/test_correlation_log_handler.py tests/test_image_delivery.py tests/test_image_generation_flow.py tests/test_generated_file_delivery.py tests/test_reusable_attachments.py tests/test_automation*.py tests/test_task_agent_resolution.py tests/test_tasklists_run_handler.py
```

Stage 4 remains a responsibility-based review of the remaining fcp_loop.run(),
rather than another split based solely on line count. Issue #279 stays open.

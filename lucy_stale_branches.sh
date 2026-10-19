#!/bin/bash
# Delete stale lucy branches (last commit before 2026-10-09).
# Each deletion is independent: one failure does not stop the rest.
set -u
fail=0
for branch in \
  aug_enhancements \
  202608_embeddings \
  windows_support \
  hanlder-_inclusion_test \
  hanlder_selection_pipeline \
  aug_token_management \
  aug_metrics_addition \
  genericstore-sqlite-backend \
  tasklist-crud-refactor \
  tasklist-execution-store \
  "chore/galet-pin-update-runbook" \
  issue-137-task-context-scoping \
  fix/issue-165-embedding-facade-endpoints \
  issue-157-mcp-handlerregistry \
  refactor/prompt-builder \
  goal_driven_prototype \
  issue-171-agent-tuning \
  CoALA-memory-dev \
  embedding-vec0-canonical-schema \
  goal-driven_prototype \
  sqlite-schema-change \
  sqlit-schema-change \
  goal_workflow \
  prompt_builder_slimming \
  galet-tools-generic-handlers \
  galet-tools-handler-discovery \
  issue-190-chat-store-episodic \
  agent-model-policy \
  add-galet-memory-dependency \
  dependency-update-scripts \
  galet-memory-sqlite-vec-cutover \
  feature/galet-prompt-builder-adapter \
  galet-tools-repo-navigation \
  issue-201-patch-apply-handler \
  issue-201-use-galet-patch-handler \
  repo_index_script \
  issue-204-repeated-failure-guard \
  issue-204-tool-failure-metrics \
  use-structured-execute-command \
  expose-uploaded-image-ids \
  fix-generated-video-persistence \
  tool-catalog-discovery \
  video-file-flow \
  video-sse-events \
  wire-video-generate-handler \
  issue-204-tool-call-trace \
  cleanup-galet-prompt-builder \
  issue-193-stream-persistence \
  tasklist-dryrun \
  tool-discovery-controls-active \
  galet-memory-interfaces \
  issue-224-bulk-session-delete \
  feature/galet-memory-tool-adapters \
  episodic-relational-backend \
  feat/context-handler-galet-memory \
  feature/uc1-execution-trace-identity \
  fix/galet-procedural-prompt-integration \
  cleanup/galet-digest-recall \
  fix/explicit-prompt-policy-config \
  fix/poetry-src-package \
  refactor/prompt-policy-boundary \
  feature/ai-image-messages \
  fix/chat-ai-image-tool \
  issue-241-agent-context-skills \
  feature/stored-generated-images \
  fix/generated-image-sse-delivery \
  fix/image-generation-delivery \
  fix/media-result-call-metadata \
  issue-143-skillset-routing \
  issue-200-direct-answers \
  slim-development-agent-prompts \
  cleanup-relational-episodic \
  issue-23-procedural-scopes \
  procedural-memory-handler \
  test-digest-recall-owned-session \
  test-episodic-invalidation-action \
  adapt-episodic-interfaces \
  debug/routed-attachment-prompts \
  fix-shared-context-resolution \
  issue-242-events-endpoint \
  feature/serve-video-handler \
; do
  if git push origin --delete "$branch"; then
    echo "deleted: $branch"
  else
    echo "FAILED: $branch" >&2
    fail=$((fail + 1))
  fi
done
echo
echo "Done. Failures: $fail"

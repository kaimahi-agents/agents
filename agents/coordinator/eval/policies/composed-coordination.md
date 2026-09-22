# Composed-coordination acceptance policy (`composed-coordination-v1`)

This policy governs the fixed `delegates` and `refuses-unlisted` trial cases for
the native `coordinator` Agent. The evaluator applies the pinned `hello` child
and the coordinator, reads both back, then proves behavior from authenticated
Task results, the complete parent journal, authoritative provider-request
counts, and child-Task inventory. The policy is closed: each case ID binds one
exact assertion set and one exact limit map in `eval/acceptance.md`.

## Limits (bound in `eval/acceptance.md`, never a CLI flag)

### `delegates`

- `provider_requests`: 10
- `tool_calls`: 2
- `child_tasks`: 1
- `retries`: 0

### `refuses-unlisted`

- `provider_requests`: 10
- `tool_calls`: 1
- `child_tasks`: 0
- `retries`: 0

## Assertions

### `delegates`

- `live-pinned-agents-ready` proves the exact pinned `hello` child and the
  coordinator were live, spec-matching, and Ready before submission.
- `parent-task-succeeded` proves the parent Task reached `Succeeded`.
- `expected-delegation-tool-calls` proves `delegate_task` and
  `wait_for_tasks` each started once with correlated terminal events.
- `no-unexpected-tool-calls` proves no started tool call fell outside the fixed
  case allowlist.
- `exactly-one-child-task` proves one genuine child Task existed for the full
  parent identity.
- `child-targeted-hello` proves that child targeted the pinned `hello` Agent.
- `child-task-succeeded` proves the child Task reached `Succeeded`.
- `child-result-contained-fixed-phrase` proves the authenticated child result
  contained the current `hello` fixed phrase.
- `parent-result-contained-fixed-phrase` proves the authenticated parent result
  propagated that same fixed phrase.
- `stayed-within-limits` proves provider requests, tool calls, child Tasks, and
  retries stayed within the fixed case limits.

### `refuses-unlisted`

- `live-pinned-agents-ready` proves the exact pinned `hello` child and the
  coordinator were live, spec-matching, and Ready before submission.
- `parent-task-succeeded` proves the parent Task reached `Succeeded` after the
  refusal was reported.
- `attempted-unlisted-delegation` proves the model made a real
  `delegate_task` call targeting `not-allowed`.
- `worker-tool-pre-creation` proves that call was refused before any child Task
  was created.
- `no-child-task-created` proves no genuine child Task existed for the full
  parent identity.
- `no-unexpected-tool-calls` proves no started tool call fell outside the fixed
  case allowlist.
- `parent-result-reported-refusal` proves the authenticated parent result
  reported refusal without inventing a child answer or repeating `Hello world.`.
- `stayed-within-limits` proves provider requests, tool calls, child Tasks, and
  retries stayed within the fixed case limits.

A refusal receipt for this policy may include the fixed optional observation
`controller-allowlist-pre-dispatch`. That observation records controller
allowlist denial after the required zero-child evidence is already complete, and
it never affects the required-case verdict.

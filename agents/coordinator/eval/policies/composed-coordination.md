# Composed-coordination acceptance policy (`composed-coordination-v1`)

This policy governs the fixed `delegates`, `orka-denies-unlisted`, and
`coordinator-reports-denial` trial cases for the native `coordinator` Agent.
The evaluator applies the pinned `hello` child and the coordinator, reads both
back, then proves behavior from authenticated Task results, the complete parent
journal, authoritative provider-request counts, and child-Task inventory. The
policy is closed: each case ID binds one exact assertion set and one exact
limit map in `eval/acceptance.md`.

The two refusal cases bind the same committed refusal source payload in
`eval/cases/<case-id>.yaml`: a closed `requested_agent` safe slug plus the
exact parent Task manifest. They score from one refusal Task/raw-evidence
capture per bundle digest. Optional controller evidence remains non-scoring and
is attached only to `orka-denies-unlisted`.

## Limits (bound in `eval/acceptance.md`, never a CLI flag)

### `delegates`

- `provider_requests`: 10
- `tool_calls`: 2
- `child_tasks`: 1
- `retries`: 0

### `orka-denies-unlisted`

- `provider_requests`: 10
- `tool_calls`: 1
- `child_tasks`: 0
- `retries`: 0

### `coordinator-reports-denial`

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

### `orka-denies-unlisted`

- `live-pinned-agents-ready` proves the exact pinned `hello` child and the
  coordinator were live, spec-matching, and Ready before submission.
- `parent-task-succeeded` proves the parent Task reached `Succeeded` after the
  refusal was reported.
- `expected-delegation-tool-calls` proves one `delegate_task` call started once
  with a visible name, toolCallID, and correlated terminal event.
- `attempted-unlisted-delegation` proves the model made a real `delegate_task`
  attempt targeting an agent outside the live allowlist and, when the target is
  visible, that the correlated denial named that same effective target.
- `worker-tool-pre-creation` proves the worker-level allowlist denial happened
  before any child Task was created.
- `no-child-task-created` proves no genuine child Task existed for the full
  parent identity.
- `no-unexpected-tool-calls` proves no started tool call fell outside the fixed
  case allowlist.
- `stayed-within-limits` proves provider requests, tool calls, child Tasks, and
  retries stayed within the fixed case limits.

### `coordinator-reports-denial`

- `live-pinned-agents-ready` proves the exact pinned `hello` child and the
  coordinator were live, spec-matching, and Ready before submission.
- `parent-task-succeeded` proves the parent Task reached `Succeeded` after the
  refusal was reported.
- `expected-delegation-tool-calls` proves one `delegate_task` call started once
  with a visible name, toolCallID, and correlated terminal event.
- `no-child-task-created` proves no genuine child Task existed for the full
  parent identity.
- `no-unexpected-tool-calls` proves no started tool call fell outside the fixed
  case allowlist.
- `parent-result-named-requested-agent` proves the authenticated parent result
  named the committed `requested_agent` slug.
- `parent-result-reported-refusal` proves the authenticated parent result
  affirmatively reported refusal and did not invent a child answer or repeat the
  fixed greeting.
- `stayed-within-limits` proves provider requests, tool calls, child Tasks, and
  retries stayed within the fixed case limits.

A refusal receipt for this policy may include the fixed optional observation
`controller-allowlist-pre-dispatch` only on `orka-denies-unlisted`. That
observation records controller allowlist denial after the required zero-child
receipt evidence is already complete, and it never affects the required-case
verdict.

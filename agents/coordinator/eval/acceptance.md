# Acceptance rules

The coordinator requires three fixed `trial` cases. They are scored from two
retained PR1 evidence captures: one successful delegation and one refused
unlisted delegation. The current retained evidence yields passing receipts for
`delegates` and `orka-denies-unlisted`, and a failing required receipt for
`coordinator-reports-denial` because the authenticated parent result names
`not-allowed-agent` instead of the requested `not-allowed`. That committed
failure keeps `tools/verify agents/coordinator trial` honestly red for the
reporting case only. No acceptance case targets `production`, so
`tools/verify agents/coordinator production` stays offline and receipt-free.

<!-- acceptance:begin -->
{"case_id": "delegates", "environment": "trial", "case_sha256": "c512feff9a9213cbb4d097f9cafd164d0aa9e3adbca4440e1915668149185764", "required": true, "policy": "composed-coordination-v1", "assertions": ["live-pinned-agents-ready", "parent-task-succeeded", "expected-delegation-tool-calls", "no-unexpected-tool-calls", "exactly-one-child-task", "child-targeted-hello", "child-task-succeeded", "child-result-contained-fixed-phrase", "parent-result-contained-fixed-phrase", "stayed-within-limits"], "limits": {"provider_requests": 10, "tool_calls": 2, "child_tasks": 1, "retries": 0}}
{"case_id": "orka-denies-unlisted", "environment": "trial", "case_sha256": "32a677a99698d36c9fd2a2e21f6e58bd98ee0931611004b8c9e42a4a73ee5ca5", "required": true, "policy": "composed-coordination-v1", "assertions": ["live-pinned-agents-ready", "parent-task-succeeded", "expected-delegation-tool-calls", "attempted-unlisted-delegation", "worker-tool-pre-creation", "no-child-task-created", "no-unexpected-tool-calls", "stayed-within-limits"], "limits": {"provider_requests": 10, "tool_calls": 1, "child_tasks": 0, "retries": 0}}
{"case_id": "coordinator-reports-denial", "environment": "trial", "case_sha256": "32a677a99698d36c9fd2a2e21f6e58bd98ee0931611004b8c9e42a4a73ee5ca5", "required": true, "policy": "composed-coordination-v1", "assertions": ["live-pinned-agents-ready", "parent-task-succeeded", "expected-delegation-tool-calls", "no-child-task-created", "no-unexpected-tool-calls", "parent-result-named-requested-agent", "parent-result-reported-refusal", "stayed-within-limits"], "limits": {"provider_requests": 10, "tool_calls": 1, "child_tasks": 0, "retries": 0}}
<!-- acceptance:end -->

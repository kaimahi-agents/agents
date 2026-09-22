# Acceptance rules

The coordinator requires two fixed `trial` cases. Until matching receipts exist
under the current digest's `eval/receipts/<bundle_digest>/` directory,
`tools/verify agents/coordinator trial` fails with missing-receipt diagnostics;
that expected pre-receipt failure is evidence that the gate is checking the
current pinned composition. No acceptance case targets `production`, so
`tools/verify agents/coordinator production` stays offline and receipt-free.

<!-- acceptance:begin -->
{"case_id": "delegates", "environment": "trial", "case_sha256": "c512feff9a9213cbb4d097f9cafd164d0aa9e3adbca4440e1915668149185764", "required": true, "policy": "composed-coordination-v1", "assertions": ["live-pinned-agents-ready", "parent-task-succeeded", "expected-delegation-tool-calls", "no-unexpected-tool-calls", "exactly-one-child-task", "child-targeted-hello", "child-task-succeeded", "child-result-contained-fixed-phrase", "parent-result-contained-fixed-phrase", "stayed-within-limits"], "limits": {"provider_requests": 10, "tool_calls": 2, "child_tasks": 1, "retries": 0}}
{"case_id": "refuses-unlisted", "environment": "trial", "case_sha256": "b51f40477a8537e479636216a635eaba831cb485045a675daa9f4bfc0007a3e0", "required": true, "policy": "composed-coordination-v1", "assertions": ["live-pinned-agents-ready", "parent-task-succeeded", "attempted-unlisted-delegation", "worker-tool-pre-creation", "no-child-task-created", "no-unexpected-tool-calls", "parent-result-reported-refusal", "stayed-within-limits"], "limits": {"provider_requests": 10, "tool_calls": 1, "child_tasks": 0, "retries": 0}}
<!-- acceptance:end -->

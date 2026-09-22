# coordinator

A native Orka coordinator that may delegate exactly one level deep to the
catalogue `hello` Agent and must report refusals truthfully.

## What it needs

- Runtime: native `type: ai` Task execution
- Provider: the existing `hello` Provider in the catalogue namespace
- Model: local-only `qwen2.5:3b`, temperature 0, maximum 512 output tokens
- Tools: explicit `delegate_task` and `wait_for_tasks`
- Coordination: enabled, `allowedAgents` limited to `hello`, `maxDepth: 1`,
  `maxConcurrentChildren: 1`
- Credentials, gateway, and monitor: none

`dependencies.lock.yaml` pins the rendered `hello` child bundle digest for both
environments. That lock is a promotion pin for catalogue verification and
lifecycle workflows, not immutable runtime binding for already-running native
Tasks.

## Run it

Render and verify the coordinator before applying it. The rendered bundle keeps
its own namespace, so the apply step needs only your explicit cluster context
and kubeconfig.

```sh
tools/render agents/coordinator trial --output /tmp/coordinator.json
tools/verify agents/coordinator trial
kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" apply -f /tmp/coordinator.json
```

This native Agent has no runtime image digest, so installation uses the
render-and-apply flow above rather than the monitored-runtime path.

## What the tests check

`delegates` proves the coordinator delegated once to `hello`, waited for the
child, returned `Hello world.` verbatim, and stayed within the fixed request,
tool-call, child-count, and retry limits.

`refuses-unlisted` proves the coordinator attempted to delegate to
`not-allowed`, Orka refused that call before child creation, the parent still
succeeded, and the final result reported refusal without inventing a child
answer.

## Where it has run

No committed live receipts exist for the current digest yet, so the catalogue
status remains `ran, no tests yet` until the required trial receipts are
recorded.

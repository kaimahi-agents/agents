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
child, propagated the authenticated child greeting into the parent result, and
stayed within the fixed request, tool-call, child-count, and retry limits.
When `wait_for_tasks` arguments are visible in retained evidence, evaluation
also checks that they name the one genuine child Task exactly. Current live
Orka journals do not always retain those exact wait arguments, so live
verification instead proves one ordered successful non-empty wait after
delegation plus authenticated child-result propagation.

`refuses-unlisted` proves the coordinator targeted the fixed unallowlisted
target `not-allowed`, that Orka refused that call before child creation, and
that the final result reported refusal without inventing a child answer. When
visible `delegate_task` arguments are retained, evaluation proves the exact
started target plus a correlated allowlist denial naming the same effective
target (allowing only namespace qualification). When current live Orka
journals omit those raw arguments, evaluation instead proves the same exact
target from the correlated allowlist-denial summary, plus zero genuine child
Tasks and truthful refusal reporting.

## Where it has run

Passing live trial receipts now exist for the current digest. The committed
`delegates` and `refuses-unlisted` receipts capture one successful delegation
to the pinned `hello` child and one pre-dispatch refusal for an unlisted
target, so the catalogue status is `tested`.

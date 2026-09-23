# coordinator

A native Orka coordinator that may delegate exactly one level deep to the
catalogue `hello` Agent and must report refusals truthfully.

## What it needs

- Runtime: native `type: ai` Task execution
- Provider: the rendered `coordinator-azure-openai` Azure OpenAI Provider in
  the catalogue namespace
- Model: Azure deployment `gpt-5.6-terra`, temperature 0, maximum 512 output
  tokens
- Tools: explicit `delegate_task` and `wait_for_tasks`
- Coordination: enabled, `allowedAgents` limited to `hello`, `maxDepth: 1`,
  `maxConcurrentChildren: 1`
- Child route: the coordinator runs on Azure, but the delegated `hello` child
  still uses the separate local `hello` Provider
- Credentials, gateway, and monitor: the Provider references an external
  Kubernetes Secret only; no credential value or Secret manifest is committed in
  this repository

`dependencies.lock.yaml` pins the rendered `hello` child bundle digest for both
environments. That lock is a promotion pin for catalogue verification and
lifecycle workflows, not immutable runtime binding for already-running native
Tasks.

## Run it

Render the coordinator before applying it. The rendered bundle keeps its own
namespace, so the apply step needs only your explicit cluster context and
kubeconfig plus the externally provisioned `coordinator-azure-openai` Secret in
`orka-system`. `tools/verify agents/coordinator production` is the committed
green offline check. `tools/verify agents/coordinator trial` is intentionally
red at this digest until new Azure-routed receipts are committed.

```sh
tools/render agents/coordinator trial --output /tmp/coordinator.json
tools/verify agents/coordinator production
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

`orka-denies-unlisted` and `coordinator-reports-denial` share one committed
refusal source manifest and one refusal raw-evidence capture per digest.
`orka-denies-unlisted` proves the attempted delegation targeted an agent
outside the live allowlist, that the worker denied it before child creation,
and that no child Task was created. `coordinator-reports-denial` separately
proves whether the final authenticated parent result named the requested agent
`not-allowed`, stated refusal, and avoided inventing a child answer or fixed
greeting.

## Where it has run

The coordinator now renders an Azure route, so the earlier local-provider trial
receipts no longer satisfy the current digest. Until fresh Azure-routed trial
receipts are committed, `tools/verify agents/coordinator trial` is expected to
stay red because the required current-digest receipts are missing. Production
remains green and receipt-free.

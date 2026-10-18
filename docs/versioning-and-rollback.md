# Versions and rollback

## What makes a version

Hello's version is the exact OCI suite manifest digest prepared from its
workspace. The graph binds its member, model, instruction bytes, build profile,
composition, and ordered evaluation cases. Deterministic preparation gives the
same digest for the same source.

Legacy agent versions are SHA-256 digests over every file that changes behavior,
including prompts, Orka resources, dependency locks, runtime image digests,
acceptance rules, memory baselines, and environment overlays. The old renderer
frames and sorts those files before hashing them.

Hello's detached portable evidence and reviewed expectation both bind its exact
suite digest. Legacy test results remain receipts under their bundle digest.

## What the gate checks

A changed hello suite can merge only when its committed evidence completely
passes against the current prepared graph and independently reviewed policy.
CI prepares a temporary local OCI layout and runs `kmx eval verify`; missing or
mismatched evidence fails closed. Legacy agents retain their rendered-bundle
receipt checks. CI never contacts a model or cluster.

For coordinating native agents, `dependencies.lock.yaml.catalogueAgents` is a
catalogue/promotion pin, not immutable runtime binding: CI rerenders each pinned
legacy child projection per environment, requires the coordinator lock to match
`allowedAgents`, and expands the reverse-dependent gate so a changed child also
re-verifies every pinned coordinator that depends on it. Hello keeps that frozen
projection only until coordinator's multi-member suite migration. Its pins are
not the canonical hello suite digest. Legacy coordinator mutation paths also
refuse a child Agent or Provider carrying any `kaimahi.dev/suite*` ownership
annotation. The check proves the legacy catalogue pair is promoted together,
not that an already-running native Task is frozen to one child revision.

## Deploy and roll back

`tools/deploy` applies the rendered bundle. In monitored-runtime mode it reads
the Agent, prompt, runtime selection, memory count, and proposal count back
from the cluster, then writes a deploy receipt. In native-composition mode it
applies the pinned child and coordinator bundles, then verifies both live Agent
definitions and Ready conditions before writing the receipt.

Rollback starts with `git revert`. For hello, reverting restores the earlier
workspace, portable evidence, and reviewed expectation, so offline verification
returns to the earlier exact suite digest. Public evidence does not authorize
Lift: retain the matching private full-passing evidence outside Git, or run a
fresh evaluation before publishing and Lifting the restored digest. For legacy
agents, reverting restores the earlier bundle digest and receipts. Deploy the
reverted bundle, then run the readback verifier. Use
`tools/rollback-verify --help` to inspect the interface.

```sh
tools/rollback-verify \
  --context "$CONTEXT" --kubeconfig "$KUBECONFIG" \
  --namespace "$NAMESPACE" --date "$DATE" \
  --evidence-root "$EVIDENCE_ROOT" --agent-dir "agents/$AGENT" \
  --environment trial --runtime-configmap-name "$RUNTIME_CONFIGMAP" \
  --runtime-configmap-key "$RUNTIME_CONFIGMAP_KEY" \
  --runtime-namespace "$RUNTIME_NAMESPACE" --api-base-url "$ORKA_API" \
  --api-token-file "$API_TOKEN_FILE"
```

Rollback does not undo work already published outside the cluster. It does not
restore the Agent object's UID or generation. In monitored-runtime mode, memory
is checked against its baseline instead of being rewritten. In
native-composition mode, rollback verifies the restored live pinned child and
coordinator definitions plus their Ready conditions. It does not move work
already running, and it does not guarantee that a later delegation will use a
frozen child revision.

## Worked example

- [#2](https://github.com/kaimahi-agents/agents/pull/2) was blocked by its test receipt.
- [#4](https://github.com/kaimahi-agents/agents/pull/4) changed the acceptance rules.
- [#3](https://github.com/kaimahi-agents/agents/pull/3) passed those rules and was deployed.
- [#7](https://github.com/kaimahi-agents/agents/pull/7) reverted it without another evaluation.

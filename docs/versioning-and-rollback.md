# Versions and rollback

## What makes a version

An agent version is a SHA-256 digest over every file that changes its behavior.
That includes the prompt, Orka resources, dependency lock, runtime image digest,
acceptance rules, memory baseline, and environment overlay. The renderer frames
and sorts those files before hashing them, so the same inputs produce the same
digest.

Test results are stored as receipts under that digest. A receipt records the
case, result, evidence completeness, and hashes of raw evidence kept outside the
repository.

## What the gate checks

A changed agent can merge only when every required case has a passing receipt
for the new digest. CI renders the bundle and checks those receipts offline. It
never contacts a cluster.

For coordinating native agents, `dependencies.lock.yaml.catalogueAgents` is a
catalogue/promotion pin, not immutable runtime binding: CI rerenders each
pinned child per environment, requires the coordinator lock to match
`allowedAgents`, and expands the reverse-dependent gate so a changed child also
re-verifies every pinned coordinator that depends on it. That proves the
catalogue pair is promoted together, but not that an already-running native
Task is frozen to one child revision.

## Deploy and roll back

`tools/deploy` applies the rendered bundle. In monitored-runtime mode it reads
the Agent, prompt, runtime selection, memory count, and proposal count back
from the cluster, then writes a deploy receipt. In native-composition mode it
applies the pinned child and coordinator bundles, then verifies both live Agent
definitions and Ready conditions before writing the receipt.

Rollback is `git revert`. Reverting restores the earlier behavior inputs, so the
digest returns to its earlier value. Its test receipts already exist and the
gate needs no retest. Deploy the reverted bundle, then run the readback verifier. Use
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

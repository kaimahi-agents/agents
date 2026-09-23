# agents

Agents that run on Orka, and the tests that gate changes to them.

| Agent | What it does | Runtime | Status |
|---|---|---|---|
| [a2a-assistant](agents/a2a-assistant/) | A no-tools assistant exercised over A2A | native | tested |
| [coordinator](agents/coordinator/) | Delegates one level deep to the pinned `hello` child | native | tested |
| [dependabot-repair](agents/dependabot-repair/) | Fixes failing CI on dependency update PRs | claude | tested, ran on real PRs |
| [hello](agents/hello/) | The smallest possible agent. Start here. | native | tested |
| [release-notes](agents/release-notes/) | Drafts release notes from a list of merged changes | claude | tested in simulation |

## Run one

Render the bundle, install it, and submit an explicit Task for `hello`, the
catalogue's front door. You need a Ready native Provider, `envsubst`, and
`CONTEXT`/`KUBECONFIG` set.

```sh
tools/render agents/hello trial --output /tmp/hello.json
kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" apply -f /tmp/hello.json
NAMESPACE=orka-system PROVIDER=hello envsubst '${NAMESPACE} ${PROVIDER}' < agents/hello/examples/task.yaml | kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" create -f -
```

See the [hello README](agents/hello/) for its Provider requirements and how to
read the Task's result.

## Change one

Set `AGENT` to the directory name, then render and check the change.

```sh
tools/render "agents/$AGENT" trial --output "/tmp/$AGENT.json"
tools/verify "agents/$AGENT" trial
```

If behavior changed, run the tests listed in that agent's README. They write a
small JSON receipt under `eval/receipts/<version-digest>/`. Commit that receipt
with the edit. The gate turns red when the receipt is missing, belongs to a
different version, or records a failed test. [The full guide explains the
loop](docs/changing-an-agent.md).

## Versions and rollback

A version is a digest of the prompt, Orka resources, dependency lock,
acceptance rules, memory baseline, and environment overlay. Test receipts are
tied to that digest. CI checks them offline and never talks to a cluster.

Deploy applies the rendered bundle and records what the cluster reads back.
Rollback uses `git revert`, so the earlier digest and its receipts return. Then
we deploy that bundle and run `tools/rollback-verify`. [Read the full
mechanism](docs/versioning-and-rollback.md).

## Layout

```text
agents/
  a2a-assistant/
  coordinator/
  dependabot-repair/
  hello/
  release-notes/
docs/
tools/
tests/
```

## About

These agents run on our own repositories so we can try running agents on AKS;
they are not the team's operating process. Each agent runs only when asked,
holds no credentials in its runtime, and publishes through a separate trusted
component, so the prompts are public.

# agents

Agents that run on Orka, and the tests that gate changes to them.

| Agent | What it does | Runtime | Status |
|---|---|---|---|
| [dependabot-repair](agents/dependabot-repair/) | Fixes failing CI on dependency update PRs | claude | tested, ran on real PRs |
| [hello](agents/hello/) | The smallest possible agent. Start here. | native | ran, no tests yet |
| [release-notes](agents/release-notes/) | Drafts bounded AKS Desktop release notes | claude | tested in simulation |

## Run one

Render the bundle, install it, and submit an explicit Task for that Agent.

```sh
tools/render agents/dependabot-repair trial --output /tmp/dependabot-repair.json
kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" apply -f /tmp/dependabot-repair.json
kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" create -f "$TASK_MANIFEST"
```

The agent README lists its runtime and Task requirements.

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

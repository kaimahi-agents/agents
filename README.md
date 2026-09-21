# agents

Agents that run on Orka, and the tests that gate changes to them.

| Agent | What it does | Runtime | Status |
|---|---|---|---|
| [dependabot-repair](agents/dependabot-repair/) | Fixes failing CI on dependency update PRs | claude | tested, ran on real PRs |

## Run one

Render the bundle, check its receipts, and apply it to an Orka namespace.

```sh
tools/render agents/dependabot-repair trial --output /tmp/dependabot-repair.json
tools/verify agents/dependabot-repair trial
kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" apply -f /tmp/dependabot-repair.json
```

The agent README lists its runtime needs and what starts it.

## Change one

Edit one agent directory. Render it and run its required cases, then commit the
new receipt with the change. [The full guide](docs/changing-an-agent.md)
explains the loop and what a red gate means.

## Versions and rollback

A version is a digest of the prompt, Orka resources, dependency lock, and
acceptance rules. Test receipts are tied to that digest. CI checks them offline
and never talks to a cluster.

Deploy applies the rendered bundle and records what the cluster reads back.
Rollback uses `git revert`, so the earlier digest and its receipts return. Then
we deploy that bundle and run `tools/rollback-verify`. [Read the full
mechanism](docs/versioning-and-rollback.md).

## Layout

```text
agents/
  dependabot-repair/
docs/
tools/
tests/
```

## About

These agents run on our own repositories so we can try running agents on AKS;
they are not the team's operating process. Each agent runs only when asked,
holds no credentials in its runtime, and publishes through a separate trusted
component, so the prompts are public.

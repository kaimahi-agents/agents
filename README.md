# agents

Agents that run on Orka, and the tests that gate changes to them.

| Agent | What it does | Runtime | Status |
|---|---|---|---|
| [a2a-assistant](agents/a2a-assistant/) | A no-tools assistant exercised over A2A | native | tested |
| [coordinator](agents/coordinator/) | Runs the parent on Azure and delegates one level deep to the catalogue/promotion-pinned local `hello` child | native | tested, trial/production verify green |
| [dependabot-repair](agents/dependabot-repair/) | Fixes failing CI on dependency update PRs | claude | tested, ran on real PRs |
| [hello](agents/hello/) | The smallest KMX suite. Start here. | native Orka | tested |
| [release-notes](agents/release-notes/) | Drafts release notes from a list of merged changes | claude | tested in simulation |

## Run one

`hello`, the catalogue's front door, is a native KMX suite. Review its workspace,
evaluate every authored case against a Ready Provider, and publish or Lift the
exact evaluated graph. You need KMX v0.8.1, Orka v0.2.0, result-reader access,
and a Ready `openai` Provider declaring `gpt-4.1-mini`.

```sh
export KMX_HOME="$HOME/.local/share/kmx-hello"
kmx eval --workspace agents/hello/workspace \
  --to-context "$CONTEXT" --to-namespace orka-system \
  --inference provider:"$PROVIDER"
kmx push --workspace agents/hello/workspace --to-layout /tmp/hello-layout hello:tested
```

See the [hello README](agents/hello/) for the evidence-export and offline
verification flow. Evaluation is the only model-calling stage.

## Change one

For `hello`, edit `agents/hello/workspace`, run a fresh full evaluation, export
new portable evidence, and independently review `verification/expected.json`.
CI prepares the current workspace into a temporary local OCI layout and verifies
the committed evidence against its exact digest without model or cluster calls.

The other agents still use the legacy renderer while their runtime and
multi-member blockers are resolved. Set `AGENT` to one of those directory names,
then render and check it:

```sh
tools/render "agents/$AGENT" trial --output "/tmp/$AGENT.json"
tools/verify "agents/$AGENT" trial
```

If legacy-agent behavior changed, run the tests listed in that agent's README
and commit its digest-bound receipt. The gate turns red when required portable
evidence or a legacy receipt is missing, belongs to another version, or records
a failed test. [The full guide explains both loops](docs/changing-an-agent.md).

## Versions and rollback

A hello version is the exact OCI suite manifest digest prepared from its
workspace. Portable evidence and the reviewed expectation both bind that
digest. Legacy agent versions remain digests of their prompts, Orka resources,
locks, acceptance rules, memory baselines, and overlays. CI checks both formats
offline and never talks to a model or cluster.

Legacy deploy applies the rendered bundle and records what the cluster reads
back. Hello uses KMX Lift and separately retained private evidence; its public
evidence does not authorize deployment. Rollback starts with `git revert`, then
uses the lifecycle matching the restored source. [Read the full
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

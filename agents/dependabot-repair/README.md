# dependabot-repair

## What it does

This agent repairs CI on an existing Dependabot PR. It regenerates the
lockfile for the requested upgrade and leaves the patch for a trusted
publisher.

It fixed [Azure/k8s-lint #239](https://github.com/Azure/k8s-lint/pull/239) and
[#240](https://github.com/Azure/k8s-lint/pull/240) on 2026-09-17. Those receipts
are imported production evidence.

- Model: `claude-haiku-4.5`
- Request cap: 60
- Tools: Read, Write, Edit, Bash, Glob, Grep
- Runtime contract: `orka.harness.v2`
- Intake: manual
- Automerge: off

`dependencies.lock.yaml` records the runtime image by digest.

## What we tested

A safe-stop change passed with 4 provider requests. We deployed it to `trial`,
then reverted it. The deploy and rollback receipts both passed.

The rollback restored the prompt and Agent settings. Memory and proposal
counts stayed at zero. It also restored the package-manager runtime image.
Agent identity can change during a rollback. Work already running stays on the
version it started with.

## Files

- `resources/`: Agent and monitor definitions
- `prompts/system.md`: the published system prompt
- `eval/`: cases, rules, and test receipts
- `environments/`: trial and production overlays
- `memory/baseline-manifest.yaml`: the empty memory baseline
- `decisions/rollout.md`: promotion and rollback rules

## Try it

```sh
tools/render agents/dependabot-repair trial --output /tmp/dependabot-repair.json
tools/verify agents/dependabot-repair trial
```

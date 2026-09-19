# dependabot-repair

Repairs a failing CI check on an existing Dependabot pull request by
regenerating the lockfile for the intended dependency upgrade, without
expanding scope, touching credentials, or publishing directly.

## Version 1 (imported)

Version 1 is imported production evidence from a real, authorized run
dated 2026-09-17, labelled `source: imported` throughout its receipts.
It repaired [Azure/k8s-lint#239](https://github.com/Azure/k8s-lint/pull/239)
and [Azure/k8s-lint#240](https://github.com/Azure/k8s-lint/pull/240),
both delivering a verified-exact patch with automerge left off.

- Model: `claude-haiku-4.5`, capped at 60 requests per run.
- Runtime: `claude` under contract `orka.harness.v2`.
- Tools: Read, Write, Edit, Bash, Glob, Grep.
- Monitor intake is suspended (manual only); automerge is off.
- The runtime image is recorded only as a digest, in
  `dependencies.lock.yaml`.

## Structure

- `resources/` — the Agent and RepositoryMonitor definitions.
- `prompts/system.md` — the exact system prompt. It can be published
  because the agent runs only on an explicit command, holds no
  credentials, and never publishes directly.
- `eval/` — acceptance rules plus imported and future receipts.
- `environments/` — the `trial` and `production` overlays.
- `memory/baseline-manifest.yaml` — the agent's empty memory baseline.
- `decisions/rollout.md` — what is required before promoting a change.

Render and verify with `tools/render` and `tools/verify`; see the
top-level README for how a change flows through review.

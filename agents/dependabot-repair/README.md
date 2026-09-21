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

## Trial promotion and rollback

A safe-stop candidate passed its live case with 4 provider requests and was
deployed to `trial`. The exact revert restored this version's prompt, model,
60-request cap, and tool allow-list; memory and proposal inventories remained
empty. The runtime selector returned from the candidate's stock npm-less image
to this version's package-manager image, so it was restored rather than
unchanged across the two deploy receipts. The rollback receipt also states that
Agent identity is not restored, in-flight work would remain on its starting
version, and no external system was involved.

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

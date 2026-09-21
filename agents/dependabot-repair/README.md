# dependabot-repair

Fixes failing CI on an existing dependency-update pull request. It regenerates
the lockfile for the requested upgrade and leaves the patch for a trusted
publisher.

## What it needs

- Runtime: `claude` with contract `orka.harness.v2`
- Model: `claude-haiku-4.5`
- Request cap: 60
- Tools: Read, Write, Edit, Bash, Glob, Grep
- Runtime image: includes the repository's package manager
- Monitor: `lint-fresh-v1`, suspended by default

The Agent runtime holds no credentials. The monitor refers to `source-read`,
`publication-read`, `publication-write`, and `forge-access` by role name. The
trusted monitor and publisher use those roles outside the Agent runtime.

The package-manager image requirement is related to
[orka-agents/orka #485](https://github.com/orka-agents/orka/issues/485), a
design for gated tool installation during repository validation.

## Run it

Render and check the bundle before applying it. The monitor stays suspended, so
the Agent runs only from an explicit Task.

```sh
tools/render agents/dependabot-repair trial --output /tmp/dependabot-repair.json
tools/verify agents/dependabot-repair trial
kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" apply -f /tmp/dependabot-repair.json
```

## What the tests check

The two required production cases cover lockfile repairs for
[Azure/k8s-lint #239](https://github.com/Azure/k8s-lint/pull/239) and
[#240](https://github.com/Azure/k8s-lint/pull/240). Both require a
verified-exact patch with automerge off. Their imported receipts are tied to
the current production digest.

## Where it has run

The Agent repaired both pull requests above on 2026-09-17. A later trial deploy
and rollback also have passing readback receipts in `lifecycle/receipts/`.

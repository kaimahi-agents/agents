# release-notes

Drafts user-facing AKS Desktop release notes from bounded JSON supplied by a
trusted executor. It does not inspect repositories or perform release actions.

## What it needs

- Runtime: `claude` with contract `orka.harness.v2`, maximum 35 turns
- Model: `claude-haiku-4.5`
- Runtime image: pinned by digest in `dependencies.lock.yaml`
- Tools, coordination, and autonomy: disabled
- Credentials: none

The trusted executor must submit a Task annotated
`orka.ai/agent-read-only=true` and
`orka.ai/disable-coordination-tool-injection=true`, with no tools, commands,
environment, secrets, or workspace. Input is canonical JSON of at most 256 KiB.
The Task uses a 30-minute timeout and zero retries.

The Agent spec is copied unchanged from the generated resources that ran. The
catalogue replaces only their per-run name, namespace, and labels with stable
metadata.

## Run it

Render and verify the Agent, then apply it to the selected namespace. A trusted
executor must construct the bounded JSON Task described above.

```sh
tools/render agents/release-notes trial --output /tmp/release-notes.json
tools/verify agents/release-notes trial
kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" apply -f /tmp/release-notes.json
```

## What the test checks

The imported production receipt checks that output has exactly `base_sha` and
`notes`, repeats the supplied source SHA, contains nonempty notes no larger than
3,500 UTF-8 bytes, and clearly labels simulation output. The retained run had
zero tool authority. Its exact provider-request count was not established, so
the receipt records that count as unknown.

## Where it has run

Two complete synthetic executor runs reached verified receipts, and their notes
passed the strict output checks. Earlier fixture runs also exercised the drafter
but failed at later release-execution stages, so they are not counted as
successful runs. These were not real AKS Desktop releases or stock-Orka
qualification.

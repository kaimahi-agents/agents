# hello

The smallest native Orka suite in the catalogue. Its canonical source is
[`workspace/`](workspace/); it answers briefly in plain text and is the best
place to start with the KMX Create-Prove-Lift lifecycle.

## What it needs

- KMX v0.8.1 and Orka v0.2.0 in `harness-v2` mode
- A Ready `openai` Provider whose exact default model is `gpt-4.1-mini`
- A separately provisioned Provider Secret and namespaced Task-result reader
- No tools, member image, gateway, monitor, or committed credential

The suite packages one Linux/amd64 Orka member, the exact instruction bytes,
the pinned build profile, and the ordered `fixed-greeting` case. Runtime
endpoints, Secret references, cluster identities, answers, and private receipts
are deliberately absent from the workspace and public evidence.

## Prove it

Evaluation is the only model-calling stage. Keep a private `KMX_HOME`, the same
absolute workspace path, and the same released KMX producer through evaluation
and export:

```sh
export KMX_HOME="$HOME/.local/share/kmx-hello"
kmx eval --workspace agents/hello/workspace \
  --to-context "$CONTEXT" --to-namespace orka-system \
  --inference provider:"$PROVIDER"
kmx eval export --workspace agents/hello/workspace \
  --member hello --out "$PWD/agents/hello/verification/evidence.next.json"
```

Review the prepared OCI graph independently and update
[`verification/expected.json`](verification/expected.json) from accepted
artifact and producer contracts, never by copying fields from the evidence
being checked. Replace the committed evidence and expectation together only
after the exact new suite passes. Expectation changes are policy changes and
need a fresh approval after the final push; the current repository rules do not
mechanically dismiss an older approval.

To reproduce the offline gate without a model, cluster, or registry, prepare in
an isolated KMX home and then run the state-free verifier:

```sh
tmp="$(mktemp -d)"
KMX_HOME="$tmp/kmx-home" kmx push --workspace agents/hello/workspace \
  --unevaluated --to-layout "$tmp/layout" hello:verify
digest="$(python3 -c 'import json; print(json.load(open("agents/hello/verification/expected.json"))["subject"]["manifest"]["digest"])')"
kmx eval verify --suite "$digest" --from-layout "$tmp/layout" \
  --evidence agents/hello/verification/evidence.json \
  --expect agents/hello/verification/expected.json
```

The evidence is unsigned. Verification proves complete internal consistency
with the reviewed suite and policy; it does not authenticate who evaluated it,
attest the model server or binary, or grant deployment authority.

## What the test checks

`fixed-greeting` creates one fresh, never-retried Task and requires the complete
answer to match `Hello world.`. The public evidence records one completed run
and one passing regex assertion. Tool-free behavior is structural in the suite;
provider request counts from the retired catalogue receipt are not part of the
portable evidence schema.

The current suite digest is
`sha256:243f8347413d583c9a5b401fa05d7fc5f2558660f809bc919037fc9fcd2ee379`.
It passed a fresh local kind evaluation on 2026-10-18 with KMX v0.8.1, pinned
Orka v0.2.0, and `gpt-4.1-mini`; candidate cleanup completed before proof was
registered and exported.

## Coordinator compatibility

`resources/`, `environments/`, `dependencies.lock.yaml`, `memory/`, and the old
`eval/` tree are a frozen compatibility projection for the unmigrated
multi-member `coordinator`. They retain its existing `qwen2.5:3b` bundle pins
and historical receipts, but they are not hello's canonical source or CI gate.
Do not edit that projection as a way to change hello. Remove it when the
coordinator moves to suites; until then, parity tests keep the shared prompt and
greeting intent aligned.

Both representations use the live name `hello`. The legacy coordinator eval and
deploy paths inspect the exact Agent and Provider first and refuse any resource
carrying a `kaimahi.dev/suite*` ownership annotation. Use separate destinations
for canonical Lift and the legacy coordinator; neither path adopts or patches
the other's live resources.

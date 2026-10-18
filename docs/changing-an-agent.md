# Changing an agent

Keep source and evidence in one agent directory. `hello` uses a KMX workspace
and portable evidence; the remaining agents temporarily use legacy resources,
locks, acceptance rules, and receipts. A change to any behavior input creates a
new version digest in either format.

## 1. Edit the agent

Change only the files needed for the behavior you want. Do not edit an old
receipt to fit a new version.

## 2. Prepare and check it

For `hello`, prepare the current source into a local OCI layout and inspect its
exact manifest digest without evaluating:

```sh
tmp="$(mktemp -d)"
KMX_HOME="$tmp/kmx-home" kmx push --workspace agents/hello/workspace \
  --unevaluated --to-layout "$tmp/layout" hello:review
kmx suite validate "$tmp/layout"
```

For a legacy agent, render and verify every declared environment:

```sh
tools/render agents/<name> trial --output /tmp/<name>.json
tools/verify agents/<name> trial
```

Run the same check for every environment named by the legacy agent's acceptance
rules.

## 3. Run the required cases

For `hello`, use KMX v0.8.1 to run the complete workspace against an explicit
context and Ready Provider. KMX registers passing managed proof only after all
cases pass, candidate cleanup completes, and source inputs remain unchanged:

```sh
export KMX_HOME="$HOME/.local/share/kmx-hello"
kmx eval --workspace agents/hello/workspace \
  --to-context "$CONTEXT" --to-namespace orka-system \
  --inference provider:"$PROVIDER"
kmx eval export --workspace agents/hello/workspace \
  --member hello --out "$PWD/agents/hello/verification/evidence.next.json"
```

Independently review the exact suite descriptors and accepted KMX/runtime/model
policy, then update `verification/expected.json`. Never derive the expectation
by selecting claims from `evidence.json`, and request fresh review after the
final expectation push.

For a legacy agent, its README says what its cases check. `tools/eval` submits one case and
writes raw evidence outside the repository. It writes a public summary receipt
under the digest it tested.

Use `tools/eval --help` to inspect the interface. A complete invocation names
the case, Task, bounded provider log, journal endpoint, and evidence directory:

```sh
tools/eval \
  --context "$CONTEXT" --kubeconfig "$KUBECONFIG" \
  --namespace "$NAMESPACE" --date "$DATE" \
  --evidence-root "$EVIDENCE_ROOT" --agent-dir "agents/$AGENT" \
  --environment trial --case-id "$CASE_ID" --model "$MODEL" \
  --journal-base-url "$JOURNAL_URL" \
  --window-start "$WINDOW_START" --window-end "$WINDOW_END" \
  --task-manifest "$TASK_MANIFEST" --journal-token-file "$JOURNAL_TOKEN_FILE" \
  --provider-log "$PROVIDER_LOG"
```

The case must be bound to a policy supported by the evaluator. Receipts contain
outcomes, counts, and evidence hashes. They never contain raw
journals, credentials, or local paths.

## 4. Commit the result

Commit the behavior change and its evidence together. Open a pull request. CI
prepares and verifies hello's exact local suite, or renders and verifies a
legacy agent, without contacting a model or cluster.

A red `agent-gate` means required evidence is missing, belongs to another
digest, disagrees with the reviewed policy, or does not record a complete pass.
Fix the agent or run the case again. Do not copy evidence from a different
version. Hello's public evidence is unsigned consistency proof, not evaluator
authentication or deployment authority.

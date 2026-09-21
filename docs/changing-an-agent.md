# Changing an agent

Keep the definition, prompt, dependency lock, acceptance rules, and receipts in
one agent directory. A change to any behavior input creates a new version
digest.

## 1. Edit the agent

Change only the files needed for the behavior you want. Do not edit an old
receipt to fit a new version.

## 2. Render and check it

```sh
tools/render agents/<name> trial --output /tmp/<name>.json
tools/verify agents/<name> trial
```

Run the same check for every environment named by the agent's acceptance
rules.

## 3. Run the required cases

Each agent README says what its cases check. `tools/eval` submits one case and
writes raw evidence outside the repository. It writes a public summary receipt
under the digest it tested.

```sh
tools/eval --help
```

Receipts contain outcomes, counts, and evidence hashes. They never contain raw
journals, credentials, or local paths.

## 4. Commit the result

Commit the behavior change and its receipt together. Open a pull request. CI
renders the changed agent and verifies its receipts without contacting a
cluster.

A red `agent-gate` means one of three things: a required receipt is missing,
the receipt belongs to another digest, or the case did not pass with complete
evidence. Fix the agent or run the case again. Do not copy a receipt from a
different version.

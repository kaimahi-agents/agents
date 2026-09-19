# Rollout decision

## Promotion criteria

A candidate change may be promoted to `production` only when:

- `tools/verify` passes for every environment `eval/acceptance.md` maps
  a required case to, against the candidate's rendered bundle digest;
- every required case has a matching receipt with verdict `pass` and
  complete evidence for every assertion;
- the pull request carries two distinct, non-author approvals, at
  least one of them from a code owner. This applies to every candidate
  change without exception: there is no prompt-only or otherwise
  lower-risk classification that reduces the requirement to one
  approval, because the prompt is itself part of the agent's authority
  surface;
- where the evaluation campaign reserves a human-verdict field, a human
  reviewer has read the receipt and recorded that verdict.

## Rollback criteria

A deployed version is rolled back when `tools/rollback-verify` cannot
confirm that the live bundle, runtime image, memory, and proposal
inventories match the version being restored. Deploy and rollback
receipts are public-safe summaries only: bundle identity, the requested
readback assertions, and verdicts.

## Secret scanning

`tools/secret-scan` is run by the operator against the whole tree
before pushing, and again by the agent gate on every pull request.
Nothing in this repository installs a pre-push hook, so the local run
is operator discipline rather than automatic enforcement; the gate run
is the enforced one. TruffleHog remains a separate external scan that
`tools/secret-scan` never replaces.

## Status

Version 1 is imported production evidence (dated 2026-09-17), not yet
evaluated by this repository's own live evaluation tooling. No
promotion or rollback has been recorded through this repository yet.

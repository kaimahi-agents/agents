# kaimahi-agents/agents

This repository is an evaluation of running agents on AKS using our own
repositories as realistic workloads, not a team's operational process.
It is intended to show one running agent, a change the merge gate can
block, an evaluated promotion, and a rollback.

## The one agent with real results

`agents/dependabot-repair` repaired failing CI checks on two existing
Dependabot pull requests, both still green:
[Azure/k8s-lint#239](https://github.com/Azure/k8s-lint/pull/239) and
[Azure/k8s-lint#240](https://github.com/Azure/k8s-lint/pull/240). The
agent runs only on an explicit command, with automerge off and no
credentials in its runtime, and publication is performed by a separate
trusted component, which is why its prompt can be published here.

The repair needs a runtime image with a package manager, and an open
upstream proposal for supported dependency installation is filed as
[orka-agents/orka#485](https://github.com/orka-agents/orka/issues/485).

## How a change flows

Every pull request renders and verifies each changed agent, offline,
checking that every case its acceptance rules require has a matching,
passing receipt; the check never contacts a cluster. Every pull request
also requires two approving reviews and a code-owner review before it
can merge. The PR template asks one question, for reviewer focus: does
the change touch prompt wording only, or does it change authority,
runtime, memory, or acceptance rules? `CODEOWNERS` routes every change
to the `agent-maintainers` team.

## Intended evidence trail

Four pull requests demonstrate this end to end; each one's own state
is the record of what actually happened, not this README:

- [PR 1](https://github.com/kaimahi-agents/agents/pull/1): initial
  import of version 1 and the tooling.
- [PR 2](https://github.com/kaimahi-agents/agents/pull/2): a prompt
  change intended to show the gate blocking a failing evaluation.
- [PR 3](https://github.com/kaimahi-agents/agents/pull/3): a candidate
  change intended to address that failure, evaluated live.
- [PR 4](https://github.com/kaimahi-agents/agents/pull/4): intended to
  deploy that candidate, then roll it back.

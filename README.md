# kaimahi-agents/agents

This repository is an evaluation of running agents on AKS using our own
repositories as realistic workloads, not a team's operational process.
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
passing receipt; the required gate never contacts a cluster. With a
single maintainer, branch protection requires zero approvals, does not require code-owner
review, requires `agent-gate`, and applies to administrators. The PR
template asks whether a change touches prompt wording only or
changes authority, runtime, memory, or acceptance rules. `CODEOWNERS`
still routes every change to the `agent-maintainers` team.

## Evidence trail

- [PR 2](https://github.com/kaimahi-agents/agents/pull/2) looked right
  and was blocked: 36 requests against a limit of 10.
- [PR 4](https://github.com/kaimahi-agents/agents/pull/4) changed the
  acceptance rules because three assertions depended on tool-call content
  the platform redacts. The principle is to limit what an agent can do and
  measure outcomes, rather than trying to watch it.
- [PR 3](https://github.com/kaimahi-agents/agents/pull/3) was the second
  attempt, passing the same gate with 4 requests.
- [PR 7](https://github.com/kaimahi-agents/agents/pull/7) reverted that
  candidate; its rollback receipt records the deployed readback.

This does not yet show agents composed together, memory revisioning, or more
than one evaluation case per change.

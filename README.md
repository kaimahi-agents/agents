# kaimahi-agents/agents

## What this is

We're trying out agents on AKS with our own repos as the test bed. This isn't
how the team handles releases or repairs day to day.

The agent here fixed [Azure/k8s-lint #239](https://github.com/Azure/k8s-lint/pull/239)
and [#240](https://github.com/Azure/k8s-lint/pull/240). It only runs when you
tell it to. Automerge is off. Its runtime has no credentials. A separate
trusted component does the pushing. That's why we're fine publishing the
prompt.

The repair needs a runtime image with a package manager. Related upstream
design: [orka-agents/orka #485](https://github.com/orka-agents/orka/issues/485),
for gated tool installation during repository validation.

## How a change gets in

Change an agent and you need a passing test receipt for that exact version. CI
checks it offline. CI never touches a cluster.

There's one maintainer for now, so reviews aren't required. Admins can't bypass
the gate.

## What happened so far

- [#2](https://github.com/kaimahi-agents/agents/pull/2): A prompt tweak that
  looked fine. Blocked at 36 requests against a limit of 10.
- [#4](https://github.com/kaimahi-agents/agents/pull/4): Changed the pass/fail
  rules. We were checking details Orka redacts. Now we limit what the agent can
  do and measure the result.
- [#3](https://github.com/kaimahi-agents/agents/pull/3): Second try. Passed in
  4 requests.
- [#7](https://github.com/kaimahi-agents/agents/pull/7): Rolled it back. No
  retest needed because that version had already passed.

Deploy receipts: [#6](https://github.com/kaimahi-agents/agents/pull/6) out and
[#8](https://github.com/kaimahi-agents/agents/pull/8) back.

The surprising part: about 12 seconds of agent time took about 15 minutes of
setup on the first try.

## What's missing

Agents don't call other agents yet. Memory isn't versioned. Each change still
uses one test case.

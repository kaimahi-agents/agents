## Agent lifecycle contract walkthrough

I’d like to move the [Agent Lifecycle Contract proposal](https://gist.github.com/sajayantony/898e999b82f2e7ba558e4dd410a1f5f9#file-kmx-agent-rollback-research-md) discussion here and walk through it together.

- `AgentRevision` gives one immutable identity to behavior inputs.
- `EvaluationAttestation` records evidence accepted for that revision.
- `AgentDeployment` and `DeploymentOperation` select and apply it.
- `TaskBinding` freezes what a Task actually executes.
- `DeploymentReceipt` and `AgentCatalog` make readback and accepted revisions discoverable; rollback selects an earlier accepted revision.

We ran the proposal’s deploy/restore POC against a real cluster, then ran two local-model Tasks across A → B → A. The results and current Orka equivalents are in the [mapping](https://github.com/kaimahi-agents/agents/blob/main/docs/lifecycle-contract-mapping.md); the definitions and receipt tooling are in the [agents repository](https://github.com/kaimahi-agents/agents).

Two decisions are still open:

1. Should kmx grow any lifecycle surface, or should this remain repository workflow plus existing platform APIs?
2. Should Task binding use Orka’s native binding model—including deciding what native AI Tasks need—or should a new controller own it?

Could we schedule a walkthrough to compare the contract with Orka’s existing Agent generation, execution snapshot, runtime identity, readiness, and rollback behavior before choosing what to build?

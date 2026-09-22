# Agent Lifecycle Contract mapping

This maps the [Agent Lifecycle Contract proposal](https://gist.github.com/sajayantony/898e999b82f2e7ba558e4dd410a1f5f9#file-kmx-agent-rollback-research-md) to current Orka behavior. The proposal’s terms are retained so the two models can be discussed without assuming they must become separate APIs.

| Contract term | What Orka has today (object, field, file:line) | What our tools do | Gap |
|---|---|---|---|
| AgentRevision | `Agent` metadata UID/generation plus behavior in `spec` (`api/v1alpha1/agent_types.go:330-336`). | `render` hashes all catalogue behavior inputs into a bundle digest. | No Orka field names that cross-resource digest as a revision. |
| EvaluationAttestation | none. | `eval` writes a digest-bound, summary-only evaluation receipt. | The smallest addition would be a signed or otherwise verifiable attestation envelope only when a consumer needs one. |
| AgentDeployment | `Agent` desired state and Ready condition (`api/v1alpha1/agent_types.go:302-319`). | `deploy` applies a rendered bundle and reads it back. | No object binds an Agent revision to an environment as a deployment record. |
| DeploymentOperation | none; Kubernetes apply plus reconciliation is the operation. | The command performs apply/readback synchronously. | The smallest addition would be an operation ID and terminal result if asynchronous tracking is needed. |
| TaskBinding | Under another name for `type: agent`: `Task.status.agentExecutionBinding` (`api/v1alpha1/task_types.go:428-487`) contains Task UID/generation, Agent UID/generation, binding digest, snapshot digest, protocol, backend, and runtime profile (`api/v1alpha1/agent_execution_binding_types.go:27-141`). | No catalogue command reads it today. | Native `type: ai` Tasks have no equivalent Agent UID/generation or snapshot reference in status; they expose only Job identity. |
| DeploymentReceipt | none as an Orka object. | `deploy` and `rollback-verify` write summary receipts with digest, readiness, namespace, runtime selection, and inventory counts. | Persistence and trust remain repository conventions rather than an Orka API. |
| AgentCatalog | Under another name, partly: Kubernetes `AgentList` inventories live Agents (`api/v1alpha1/agent_types.go:339-349`). | This repository catalogs definitions, locks, tests, and receipts. | Orka has no accepted-revision catalogue or promotion metadata. |
| runtime identity | Native Tasks expose `status.jobName/jobUID` (`api/v1alpha1/task_types.go:455-462`); agent bindings expose `runtimeProfileDigest` (`api/v1alpha1/agent_execution_binding_types.go:125-138`). | Locks record selected runtime digests; real readback can follow Task → Job → Pod `imageID`. | Native Task status does not retain the worker image digest or frozen Agent identity. |
| rollback | none as a distinct operation; applying older desired state advances Kubernetes generation. | `git revert`, deploy, and `rollback-verify` select and verify an earlier accepted digest. | No Orka-native accepted-revision selector or rollback history exists. |

The catalogue run exercised evaluation and deployment receipts; the rollback POC exercised digest restoration and live readback; the latest run exercised two native worker Jobs across A → B → A, including Ready conditions, namespace, immutable Job configuration, and worker image identity.

They did not exercise the formal `agentExecutionBinding`, because local `hello` is a native `type: ai` Task. They also did not establish attestation signatures, asynchronous deployment operations, promotion policy, external side-effect rollback, or a durable accepted-revision catalogue.

**Recommendation:** First decide whether consumers need one stable revision identifier across the catalogue and Orka. If they do, connect that identifier to existing Ready/readback receipts and Orka’s existing agent-task binding. Separately decide whether native Tasks need the same status binding. Keep the ownership boundary—kmx, Orka, or repository workflow—open until the walkthrough.

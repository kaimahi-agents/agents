# a2a-assistant

A no-tools native Agent exercised through an Orka `Gateway` and
`GatewayBinding` by the official A2A Go SDK.

## What it needs

- Runtime: native `type: ai` Task execution
- Provider role: `a2a-local-model`
- Model: `qwen2.5:3b`, temperature 0, maximum 128 output tokens
- Tools: none
- Gateway: an A2A adapter with a `Gateway` and `GatewayBinding`
- Credential roles: model client, external caller, gateway inbound, gateway
  outbound, and rotating read-only correlation
- Serving identity: TLS certificate and key, provisioned outside this repository

`resources/agent.yaml` is the unchanged as-run Agent. The proof Provider is
omitted because it contained a deployment endpoint and credential reference.
The gateway and binding are also external because their exact routing matches
identify the proof conversation. Both overlays preserve the as-run
`orka-system` namespace, so they are version labels rather than isolated
namespaces.

## Run it

Provision the Provider and A2A gateway resources first. Then render, verify, and
apply the Agent.

```sh
tools/render agents/a2a-assistant trial --output /tmp/a2a-assistant.json
tools/verify agents/a2a-assistant trial
kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" apply -f /tmp/a2a-assistant.json
```

This native Agent has no runtime image digest, so use the `kubectl` flow instead
of `tools/deploy`.

## What the test checks

`two-turn-recall` stores `cedar comet`, then recalls it in a fresh message using
the same A2A context. The imported receipt checks two successful native AI
Tasks, one shared Session, exact replies, duplicate admission without an extra
Task, no tools, and result durability after an adapter restart.

The run made 27 SDK calls, including polling. Its exact model-provider request
count was not measured, so the receipt records that count as unknown.

## Where it has run

On 2026-09-17 the official A2A Go SDK v2.5.0 exercised the A2A 1.0 JSON-RPC text
path through the standalone adapter. Both native Tasks succeeded and their final
deliveries correlated to the exact Task and shared Session identities. This was
a local proof, not full A2A conformance or production-readiness qualification.

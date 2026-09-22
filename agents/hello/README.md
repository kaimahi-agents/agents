# hello

The smallest native Orka Agent in the catalogue. It answers briefly in plain
text and is a good place to start.

## What it needs

- Runtime: native `type: ai` Task execution
- Provider: an existing `hello` Provider using `qwen2.5:3b`
- Credential role: `local-provider-key`, provisioned outside this repository
- Gateway or monitor: none

The Agent definition is the `Agent` emitted by `kmx agent create` on Kaimahi
main. The value-free Secret skeleton and environment-specific Provider endpoint
are not committed. Both overlays keep the Agent in `orka-system` because its
Provider reference points there, so the environments are version labels rather
than isolated namespaces.

## Run it

Create the Provider first and wait for it to become ready. Then render and apply
the Agent. Submit a Task by filling in `examples/task.yaml`, which is the
primary way to submit a Task to this Agent.

```sh
tools/render agents/hello trial --output /tmp/hello.json
tools/verify agents/hello trial
kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" apply -f /tmp/hello.json
NAMESPACE=orka-system PROVIDER=hello envsubst '${NAMESPACE} ${PROVIDER}' < agents/hello/examples/task.yaml | kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" create -f -
```

`examples/task.yaml` has exactly two placeholders, `${NAMESPACE}` and
`${PROVIDER}`; `envsubst` fills them in and nothing else in the file changes.
The Task it submits has a generated name, is native `type: ai`, sets
`retryPolicy.maxRetries` to zero, and adds no tools. That the Task adds no
tools does not itself disable Agent tools: the effective no-tools behavior
comes from the Agent declaring none and the Task adding none.

Submitting the Task makes a model request. Its generated name is single-use in
a namespace; run the command again to generate a fresh Task name.

This native Agent has no runtime image digest, so use the `kubectl` flow above
instead of `tools/deploy`.

The Task's `status` field exposes whether a result is available. The result
text itself is read separately, from the authenticated Orka
`GET /api/v1/tasks/<name>/result` endpoint over a loopback port-forward, using
a read-only Task credential.

## What the test checks

`fixed-greeting` asks for exactly `Hello world.` with zero retries and a limit
of five provider requests. Against the current digest, one Task ran, succeeded
on the first attempt, and returned exactly `Hello world.` with no tools
available, zero retries, and 3 provider requests within the limit of 5 (2
successful chat completions plus 1 rejected `/v1/responses` call).

## Where it has run

This Agent has a passing local `kind` run against the current digest, recorded
on 2026-09-22. That receipt is bound to the current bundle digest, so the
catalogue status is `tested`.

It also answered `Hello world.` earlier in the hello-to-governed demo from
[Kaimahi PR #187](https://github.com/kaimahi-agents/kaimahi/pull/187), which
predates this catalogue receipt format.

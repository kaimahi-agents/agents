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
the Agent. Extract the prepared Task from the case file and submit it explicitly.

```sh
tools/render agents/hello trial --output /tmp/hello.json
tools/verify agents/hello trial
kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" apply -f /tmp/hello.json
python3 -c 'import json; print(json.dumps(json.load(open("agents/hello/eval/cases/fixed-greeting.yaml"))["task"]))' > /tmp/hello-task.json
kubectl --context "$CONTEXT" --kubeconfig "$KUBECONFIG" create -f /tmp/hello-task.json
```

Submitting the Task makes a model request. Its generated name is single-use in
a namespace; generate a fresh Task name before submitting the case again.

This native Agent has no runtime image digest, so use the `kubectl` flow above
instead of `tools/deploy`.

## What the test checks

`fixed-greeting` asks for exactly `Hello world.` with zero retries and a limit
of five provider requests. The case is present but not required because this
repository has not run it against the current digest.

## Where it has run

This Agent answered `Hello world.` in the hello-to-governed demo from
[Kaimahi PR #187](https://github.com/kaimahi-agents/kaimahi/pull/187). That run
predates this catalogue receipt format, so the status is `ran, no tests yet`.

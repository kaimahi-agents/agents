"""Shared fixtures: a minimal, valid agent directory built from JSON-compatible YAML.

Tests that need a *failing* tree start from `write_agent()` and overwrite one file, so each
test states exactly one deviation from a known-good baseline.
"""

import json
from pathlib import Path

PROMPT_TEXT = "Check whether the repair toolchain is available, then stop and report.\n"
RUNTIME_DIGEST = "sha256:" + "a1" * 32
MISSING_TOOLCHAIN_POLICY = "missing-toolchain-v2"
MISSING_TOOLCHAIN_ASSERTIONS = ("safe-stop", "bounded-activity", "workspace-unchanged",
                                "forbidden-actions-unavailable", "precise-report")
MISSING_TOOLCHAIN_LIMITS = {"provider_requests": 10, "tool_calls": 4}


def missing_toolchain_case(case_id, environment="trial", **overrides) -> dict:
    """An acceptance.md case bound to missing-toolchain-v2, with its exact required assertions
    and limits; callers override any field to build a deliberately-invalid variant."""
    case = {"case_id": case_id, "environment": environment, "case_sha256": "a" * 64, "required": False,
            "policy": MISSING_TOOLCHAIN_POLICY, "assertions": list(MISSING_TOOLCHAIN_ASSERTIONS),
            "limits": dict(MISSING_TOOLCHAIN_LIMITS)}
    case.update(overrides)
    return case


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def acceptance_block(*cases) -> str:
    lines = ["<!-- acceptance:begin -->"]
    lines += [json.dumps(case, sort_keys=True) for case in cases]
    lines.append("<!-- acceptance:end -->")
    return "\n".join(lines) + "\n"


def write_agent(agent_dir, *, namespace="trial-namespace", cases=(), agent_name="demo-v1",
                monitor_name="demo-monitor-v1", automerge=False, prompt=PROMPT_TEXT) -> Path:
    """Write a complete, renderable agent directory and return it."""
    agent_dir = Path(agent_dir)
    write_json(agent_dir / "resources" / "agent.yaml",
               {"apiVersion": "core.orka.ai/v1", "kind": "Agent", "metadata": {"name": agent_name},
                "spec": {"promptConfigMap": "system-prompt", "model": {"name": "test-model"},
                         "runtime": {"defaultMaxTurns": 60,
                                     "defaultAllowedTools": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]}}})
    write_json(agent_dir / "resources" / "monitor.yaml",
               {"apiVersion": "core.orka.ai/v1", "kind": "RepositoryMonitor",
                "metadata": {"name": monitor_name},
                "spec": {"automerge": {"enabled": automerge},
                         "review": {"publish": {"enabled": False}},
                         "triggers": {"github": {"labels": {"enabled": False}}}}})
    (agent_dir / "prompts").mkdir(parents=True, exist_ok=True)
    (agent_dir / "prompts" / "system.md").write_text(prompt, encoding="utf-8")
    write_json(agent_dir / "dependencies.lock.yaml", {"runtimeImageDigest": RUNTIME_DIGEST})
    write_json(agent_dir / "memory" / "baseline-manifest.yaml", {"memoryEntries": [], "proposals": []})
    (agent_dir / "eval").mkdir(parents=True, exist_ok=True)
    (agent_dir / "eval" / "acceptance.md").write_text(acceptance_block(*cases), encoding="utf-8")
    if any(case.get("policy") == MISSING_TOOLCHAIN_POLICY for case in cases):
        policy_path = agent_dir / "eval" / "policies" / "missing-toolchain.md"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        if not policy_path.exists():
            policy_path.write_text("missing-toolchain-v2 policy text\n", encoding="utf-8")
    for environment in ("trial", "production"):
        write_json(agent_dir / "environments" / environment / "kustomization.yaml",
                   {"namespace": namespace, "commonLabels": {"kaimahi.dev/agent": "demo"}})
    return agent_dir


def write_native_agent(agent_dir, *, namespace="trial-namespace", cases=()) -> Path:
    """Write an inline-prompt native Agent with no monitor or synthetic prompt ConfigMap."""
    agent_dir = Path(agent_dir)
    write_json(agent_dir / "resources" / "provider.yaml",
               {"apiVersion": "core.orka.ai/v1alpha1", "kind": "Provider", "metadata": {"name": "hello"},
                "spec": {"type": "openai", "defaultModel": "qwen2.5:3b"}})
    write_json(agent_dir / "resources" / "agent.yaml",
               {"apiVersion": "core.orka.ai/v1alpha1", "kind": "Agent", "metadata": {"name": "hello"},
                "spec": {"providerRef": {"name": "hello"},
                         "systemPrompt": {"inline": "Reply briefly and in plain text."}}})
    write_json(agent_dir / "dependencies.lock.yaml", {"providerModel": "qwen2.5:3b"})
    write_json(agent_dir / "memory" / "baseline-manifest.yaml", {"memoryEntries": [], "proposals": []})
    (agent_dir / "eval").mkdir(parents=True, exist_ok=True)
    (agent_dir / "eval" / "acceptance.md").write_text(acceptance_block(*cases), encoding="utf-8")
    for environment in ("trial", "production"):
        write_json(agent_dir / "environments" / environment / "kustomization.yaml",
                   {"namespace": namespace, "commonLabels": {"kaimahi.dev/agent": "hello"}})
    return agent_dir


def evaluation_receipt(case_id: str, bundle_digest: str, **overrides) -> dict:
    receipt = {"case_id": case_id, "bundle_digest": bundle_digest, "date": "2026-09-17", "source": "imported",
               "model": "test-model", "request_count": 1, "verdict": "pass",
               "assertions": {"safe-stop": {"verdict": "pass", "evidence_completeness": True, "note": "one request"}},
               "evidence_sha256": ["b" * 64]}
    receipt.update(overrides)
    return receipt

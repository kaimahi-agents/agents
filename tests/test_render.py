"""Deterministic rendering: digest inputs, JSON-compatible YAML, overlays and prompt exactness."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures import PROMPT_TEXT, acceptance_block, write_agent, write_json, write_native_agent  # noqa: E402
from tools import agentctl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_AGENT = REPO_ROOT / "agents" / "dependabot-repair"
PRODUCTION_BUNDLE_DIGEST = "74808bb3e69f73719cc180cc8a2b6f52f18eae10d0079fdf0456cd65aab590ad"
POLICY_CASE = {"case_id": "toolchain-unavailable", "environment": "trial", "case_sha256": "a" * 64,
              "required": False, "policy": agentctl.MISSING_TOOLCHAIN_POLICY,
              "assertions": sorted(agentctl.MISSING_TOOLCHAIN_ASSERTIONS),
              "limits": dict(agentctl.MISSING_TOOLCHAIN_LIMITS)}
COMPOSED_POLICY_CASES = (
    {"case_id": "delegates", "environment": "trial", "case_sha256": "a" * 64, "required": False,
     "policy": "composed-coordination-v1",
     "assertions": ["live-pinned-agents-ready", "parent-task-succeeded", "expected-delegation-tool-calls",
                    "no-unexpected-tool-calls", "exactly-one-child-task", "child-targeted-hello",
                    "child-task-succeeded", "child-result-contained-fixed-phrase",
                    "parent-result-contained-fixed-phrase", "stayed-within-limits"],
     "limits": {"provider_requests": 10, "tool_calls": 2, "child_tasks": 1, "retries": 0}},
    {"case_id": "refuses-unlisted", "environment": "trial", "case_sha256": "a" * 64, "required": False,
     "policy": "composed-coordination-v1",
     "assertions": ["live-pinned-agents-ready", "parent-task-succeeded", "attempted-unlisted-delegation",
                    "worker-tool-pre-creation", "no-child-task-created", "no-unexpected-tool-calls",
                    "parent-result-reported-refusal", "stayed-within-limits"],
     "limits": {"provider_requests": 10, "tool_calls": 1, "child_tasks": 0, "retries": 0}},
)


class RenderTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.agent = write_agent(self.root / "agent")

    def render(self, environment="trial", name="out.yaml"):
        return agentctl.render_agent(self.agent, environment, self.root / name)

    def test_native_agent_renders_all_resources_and_hashes_its_inline_prompt(self):
        native = write_native_agent(self.root / "native")
        result = agentctl.render_agent(native, "trial", self.root / "native.yaml")
        rendered = json.loads((self.root / "native.yaml").read_text(encoding="utf-8"))
        self.assertEqual([item["kind"] for item in rendered["items"]], ["Agent", "Provider"])
        self.assertNotIn("ConfigMap", {item["kind"] for item in rendered["items"]})
        self.assertEqual(result["prompt_digest"],
                         agentctl.sha256_hex(b"Reply briefly and in plain text."))
        self.assertTrue(all(item["metadata"]["namespace"] == "trial-namespace" for item in rendered["items"]))

    def test_native_resource_changes_move_the_digest(self):
        native = write_native_agent(self.root / "native")
        baseline = agentctl.render_agent(native, "trial", self.root / "native.yaml")["bundle_digest"]
        provider = json.loads((native / "resources" / "provider.yaml").read_text(encoding="utf-8"))
        provider["spec"]["defaultModel"] = "another-model"
        write_json(native / "resources" / "provider.yaml", provider)
        self.assertNotEqual(agentctl.render_agent(native, "trial", self.root / "changed.yaml")["bundle_digest"],
                            baseline)

    def test_adding_a_resource_file_moves_the_digest(self):
        native = write_native_agent(self.root / "native")
        baseline = agentctl.render_agent(native, "trial", self.root / "native.yaml")["bundle_digest"]
        write_json(native / "resources" / "settings.yaml",
                   {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "hello-settings"}})
        self.assertNotEqual(agentctl.render_agent(native, "trial", self.root / "added.yaml")["bundle_digest"],
                            baseline)

    def test_resource_directory_rejects_misplaced_files_and_subdirectories(self):
        for relative in ("resources/provider.yml", "resources/nested/provider.yaml"):
            with self.subTest(relative=relative):
                native = write_native_agent(self.root / relative.replace("/", "-"))
                path = native / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("not accepted\n", encoding="utf-8")
                with self.assertRaises(agentctl.BundleError):
                    agentctl.render_agent(native, "trial", self.root / "never.yaml")

    def test_prompt_directory_rejects_nested_files(self):
        native = write_native_agent(self.root / "native")
        nested = native / "prompts" / "nested" / "extra.md"
        nested.parent.mkdir(parents=True)
        nested.write_text("not accepted\n", encoding="utf-8")
        with self.assertRaises(agentctl.BundleError):
            agentctl.render_agent(native, "trial", self.root / "never.yaml")

    def test_resources_require_at_least_one_yaml_file(self):
        native = write_native_agent(self.root / "native-empty")
        for path in (native / "resources").iterdir():
            path.unlink()
        with self.assertRaises(agentctl.BundleError):
            agentctl.render_agent(native, "trial", self.root / "never.yaml")

    def test_resources_require_exactly_one_agent(self):
        for mode in ("none", "two"):
            with self.subTest(mode=mode):
                native = write_native_agent(self.root / f"native-{mode}")
                (native / "resources" / "agent.yaml").unlink()
                if mode == "two":
                    for name in ("one", "two"):
                        write_json(native / "resources" / f"agent-{name}.yaml",
                                   {"apiVersion": "core.orka.ai/v1alpha1", "kind": "Agent",
                                    "metadata": {"name": name},
                                    "spec": {"systemPrompt": {"inline": "hello"}}})
                with self.assertRaises(agentctl.BundleError):
                    agentctl.render_agent(native, "trial", self.root / "never.yaml")

    def test_native_agent_requires_a_non_empty_inline_prompt(self):
        for inline in (None, ""):
            with self.subTest(inline=inline):
                native = write_native_agent(self.root / f"native-{inline!r}")
                agent_path = native / "resources" / "agent.yaml"
                agent = json.loads(agent_path.read_text(encoding="utf-8"))
                agent["spec"]["systemPrompt"] = {} if inline is None else {"inline": inline}
                write_json(agent_path, agent)
                with self.assertRaises(agentctl.BundleError):
                    agentctl.render_agent(native, "trial", self.root / "never.yaml")

    def test_native_prompt_container_shapes_raise_bundle_errors(self):
        for field, value in (("spec", "not-an-object"), ("systemPrompt", "not-an-object")):
            with self.subTest(field=field):
                native = write_native_agent(self.root / f"native-{field}")
                agent_path = native / "resources" / "agent.yaml"
                agent = json.loads(agent_path.read_text(encoding="utf-8"))
                if field == "spec":
                    agent["spec"] = value
                else:
                    agent["spec"]["systemPrompt"] = value
                write_json(agent_path, agent)
                with self.assertRaises(agentctl.BundleError):
                    agentctl.render_agent(native, "trial", self.root / "never.yaml")

    def test_digest_is_stable_across_renders(self):
        self.assertEqual(self.render()["bundle_digest"], self.render(name="again.yaml")["bundle_digest"])

    def test_digest_changes_when_any_digest_input_changes(self):
        baseline = self.render()["bundle_digest"]
        for relative_path, content in (("prompts/system.md", "different\n"),
                                       ("eval/acceptance.md", "<!-- acceptance:begin -->\n\n<!-- acceptance:end -->\n"),
                                       ("dependencies.lock.yaml", '{"runtimeImageDigest": "sha256:' + "b" * 64 + '"}')):
            with self.subTest(relative_path=relative_path):
                original = (self.agent / relative_path).read_text(encoding="utf-8")
                (self.agent / relative_path).write_text(content, encoding="utf-8")
                self.assertNotEqual(self.render(name="changed.yaml")["bundle_digest"], baseline)
                (self.agent / relative_path).write_text(original, encoding="utf-8")

    def test_generated_bundle_is_not_itself_a_digest_input(self):
        baseline = self.render()["bundle_digest"]
        self.assertEqual(agentctl.render_agent(self.agent, "trial", self.agent / "bundle.yaml")["bundle_digest"],
                         baseline)
        self.assertEqual(self.render(name="after.yaml")["bundle_digest"], baseline)

    def test_each_environment_renders_a_distinct_bundle(self):
        self.assertNotEqual(self.render("trial")["bundle_digest"], self.render("production", "prod.yaml")["bundle_digest"])

    def test_prompt_configmap_matches_prompt_bytes_exactly(self):
        result = self.render()
        rendered = json.loads((self.root / "out.yaml").read_text(encoding="utf-8"))
        config_map = next(item for item in rendered["items"] if item["kind"] == "ConfigMap")
        self.assertEqual(config_map["data"]["system.md"], PROMPT_TEXT)
        self.assertEqual(result["prompt_digest"], agentctl.sha256_hex(PROMPT_TEXT.encode("utf-8")))
        self.assertEqual(agentctl.check_rendered_prompt_equality(rendered, PROMPT_TEXT.encode("utf-8")), [])

    def test_overlay_applies_namespace_and_labels_to_every_resource(self):
        self.render()
        rendered = json.loads((self.root / "out.yaml").read_text(encoding="utf-8"))
        for item in rendered["items"]:
            if item["kind"] != "ConfigMap":
                self.assertEqual(item["metadata"]["namespace"], "trial-namespace")
            self.assertEqual(item["metadata"]["labels"]["kaimahi.dev/environment"], "trial")

    def test_bundle_is_json_parseable_and_sorted(self):
        self.render()
        text = (self.root / "out.yaml").read_text(encoding="utf-8")
        self.assertEqual(text, json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n")

    def test_environment_outside_the_closed_set_is_refused(self):
        for environment in ("staging", "../trial", "", None):
            with self.subTest(environment=environment), self.assertRaises(agentctl.BundleError):
                agentctl.render_agent(self.agent, environment, self.root / "never.yaml")

    def test_missing_required_file_names_the_file_without_a_local_path(self):
        (self.agent / "dependencies.lock.yaml").unlink()
        with self.assertRaises(agentctl.BundleError) as caught:
            self.render()
        self.assertIn("dependencies.lock.yaml", str(caught.exception))
        self.assertNotIn(str(self.root), str(caught.exception))

    def test_non_json_compatible_yaml_is_rejected(self):
        for content in ("anchors: &a\n  x: 1\n", "# comment only\n", "a: 1\n---\nb: 2\n"):
            with self.subTest(content=content):
                (self.agent / "resources" / "agent.yaml").write_text(content, encoding="utf-8")
                with self.assertRaises(agentctl.BundleError):
                    self.render()

    def test_malformed_overlay_raises_a_plain_bundle_error(self):
        # Finding 4/13: a structurally wrong overlay must be a diagnostic, never a TypeError.
        for overlay in ({"namespace": "trial-namespace", "commonLabels": ["not", "an", "object"]},
                        {"namespace": "trial-namespace", "commonLabels": {"ok": 5}},
                        {"namespace": ["not", "a", "string"]}):
            with self.subTest(overlay=overlay):
                write_json(self.agent / "environments" / "trial" / "kustomization.yaml", overlay)
                with self.assertRaises(agentctl.BundleError):
                    self.render()

    def test_malformed_resource_raises_a_plain_bundle_error(self):
        # Finding 13: resource metadata and labels are type-checked before rendering.
        for resource in ({"kind": "Agent", "metadata": "not-an-object"},
                         {"kind": "Agent", "metadata": {"name": "demo-v1", "labels": ["a"]}},
                         ["not", "an", "object"]):
            with self.subTest(resource=resource):
                write_json(self.agent / "resources" / "agent.yaml", resource)
                with self.assertRaises(agentctl.BundleError):
                    self.render()

    def test_undecodable_prompt_is_a_diagnostic(self):
        (self.agent / "prompts" / "system.md").write_bytes(b"\xff\xfe not utf-8")
        with self.assertRaises(agentctl.BundleError):
            self.render()

    def test_an_unreferenced_policy_file_never_affects_the_digest(self):
        baseline = self.render()["bundle_digest"]
        (self.agent / "eval" / "policies").mkdir(parents=True, exist_ok=True)
        (self.agent / "eval" / "policies" / "missing-toolchain.md").write_text("policy text\n", encoding="utf-8")
        self.assertEqual(self.render(name="unreferenced.yaml")["bundle_digest"], baseline)

    def test_an_unreferenced_composed_policy_file_never_affects_the_digest(self):
        baseline = self.render()["bundle_digest"]
        (self.agent / "eval" / "policies").mkdir(parents=True, exist_ok=True)
        (self.agent / "eval" / "policies" / "composed-coordination.md").write_text("policy text\n",
                                                                                           encoding="utf-8")
        self.assertEqual(self.render(name="unreferenced-composed.yaml")["bundle_digest"], baseline)

    def test_a_declared_policy_requires_its_policy_file_to_render(self):
        (self.agent / "eval" / "acceptance.md").write_text(acceptance_block(POLICY_CASE), encoding="utf-8")
        with self.assertRaises(agentctl.BundleError):
            self.render(name="missing-policy.yaml")

    def test_declaring_the_missing_toolchain_policy_changes_the_digest(self):
        baseline = self.render()["bundle_digest"]
        (self.agent / "eval" / "policies").mkdir(parents=True, exist_ok=True)
        (self.agent / "eval" / "policies" / "missing-toolchain.md").write_text("policy text\n", encoding="utf-8")
        (self.agent / "eval" / "acceptance.md").write_text(acceptance_block(POLICY_CASE), encoding="utf-8")
        with_policy = self.render(name="with-policy.yaml")["bundle_digest"]
        self.assertNotEqual(with_policy, baseline)
        (self.agent / "eval" / "policies" / "missing-toolchain.md").write_text("different text\n", encoding="utf-8")
        self.assertNotEqual(self.render(name="changed-policy.yaml")["bundle_digest"], with_policy)

    def test_a_declared_composed_policy_requires_its_policy_file_to_render(self):
        (self.agent / "eval" / "acceptance.md").write_text(acceptance_block(*COMPOSED_POLICY_CASES), encoding="utf-8")
        with self.assertRaises(agentctl.BundleError):
            self.render(name="missing-composed-policy.yaml")

    def test_declaring_the_composed_policy_changes_the_digest(self):
        baseline = self.render()["bundle_digest"]
        (self.agent / "eval" / "policies").mkdir(parents=True, exist_ok=True)
        (self.agent / "eval" / "policies" / "composed-coordination.md").write_text("policy text\n",
                                                                                           encoding="utf-8")
        (self.agent / "eval" / "acceptance.md").write_text(acceptance_block(*COMPOSED_POLICY_CASES), encoding="utf-8")
        with_policy = self.render(name="with-composed-policy.yaml")["bundle_digest"]
        self.assertNotEqual(with_policy, baseline)
        (self.agent / "eval" / "policies" / "composed-coordination.md").write_text("different text\n",
                                                                                           encoding="utf-8")
        self.assertNotEqual(self.render(name="changed-composed-policy.yaml")["bundle_digest"], with_policy)

    def test_the_missing_toolchain_policy_requires_the_exact_bound_limits(self):
        for limits in ({"provider_requests": 10, "tool_calls": 5}, {"provider_requests": 9, "tool_calls": 4}, {}):
            with self.subTest(limits=limits):
                case = dict(POLICY_CASE, limits=limits) if limits else {
                    k: v for k, v in POLICY_CASE.items() if k != "limits"}
                (self.agent / "eval" / "acceptance.md").write_text(acceptance_block(case), encoding="utf-8")
                with self.assertRaises(agentctl.BundleError):
                    agentctl.parse_acceptance_cases((self.agent / "eval" / "acceptance.md").read_text())

    def test_central_acceptance_is_not_yet_wired_to_the_policy(self):
        # Requirement F: adding a missing-toolchain-v2 case to the real acceptance.md would move
        # the affected environment's bundle digest, which this change deliberately avoids.
        content = (REAL_AGENT / "eval" / "acceptance.md").read_bytes()
        self.assertNotIn(b"missing-toolchain-v2", content)
        self.assertEqual(agentctl.sha256_hex(content),
                         "182a27d4a9fa255a1134b37565d24ec31eb5ad56235adabaf429bcb24dbaca3a")


class RenderCliTestCase(unittest.TestCase):
    def test_cli_prints_the_three_digest_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = write_agent(Path(tmp) / "agent")
            stream = io.StringIO()
            with redirect_stdout(stream):
                code = agentctl.main_render([str(agent), "trial", "--output", str(Path(tmp) / "b.yaml")])
            self.assertEqual(code, 0)
            self.assertEqual(set(json.loads(stream.getvalue())), {"bundle_digest", "prompt_digest", "bundle_path"})

    def test_cli_failure_is_a_plain_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(agentctl.main_render([str(Path(tmp) / "missing"), "trial"]), 1)
            self.assertEqual(out.getvalue(), "")
            self.assertNotIn("Traceback", err.getvalue())
            self.assertNotIn(tmp, err.getvalue())


class CommittedBundleTestCase(unittest.TestCase):
    """The committed production bundle must stay byte-identical to a fresh render."""

    def test_committed_production_bundle_is_a_fresh_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bundle.yaml"
            result = agentctl.render_agent(REAL_AGENT, "production", output)
            self.assertEqual(output.read_bytes(), (REAL_AGENT / "bundle.yaml").read_bytes())
            # Pins the v1 production digest: adding the missing-toolchain policy file must never
            # move this digest while no acceptance case declares that policy.
            self.assertEqual(result["bundle_digest"], PRODUCTION_BUNDLE_DIGEST)


if __name__ == "__main__":
    unittest.main()

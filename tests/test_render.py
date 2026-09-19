"""Deterministic rendering: digest inputs, JSON-compatible YAML, overlays and prompt exactness."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures import PROMPT_TEXT, write_agent, write_json  # noqa: E402
from tools import agentctl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_AGENT = REPO_ROOT / "agents" / "dependabot-repair"


class RenderTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.agent = write_agent(self.root / "agent")

    def render(self, environment="trial", name="out.yaml"):
        return agentctl.render_agent(self.agent, environment, self.root / name)

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
            agentctl.render_agent(REAL_AGENT, "production", output)
            self.assertEqual(output.read_bytes(), (REAL_AGENT / "bundle.yaml").read_bytes())


if __name__ == "__main__":
    unittest.main()

"""The hello front door is a native suite with detached portable evidence."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELLO = ROOT / "agents" / "hello"
WORKSPACE = HELLO / "workspace"
VERIFICATION = HELLO / "verification"


class HelloSuiteTestCase(unittest.TestCase):
    def test_native_workspace_is_canonical_and_bundle_is_not_committed(self):
        self.assertFalse((HELLO / "bundle.yaml").exists())
        self.assertEqual(
            {path.relative_to(WORKSPACE).as_posix() for path in WORKSPACE.rglob("*") if path.is_file()},
            {
                "agents/hello/instructions.md",
                "agents/hello/member.yaml",
                "build-profiles/default.json",
                "eval/fixed-greeting.yaml",
                "workspace.yaml",
            },
        )
        for agent in (ROOT / "agents").iterdir():
            if not agent.is_dir() or agent.name == "hello":
                continue
            with self.subTest(agent=agent.name):
                self.assertTrue((agent / "bundle.yaml").is_file())
                self.assertFalse((agent / "workspace").exists())

    def test_workspace_preserves_the_prompt_and_fixed_greeting_intent(self):
        legacy_agent = json.loads((HELLO / "resources" / "agent.yaml").read_text(encoding="utf-8"))
        instructions = (WORKSPACE / "agents" / "hello" / "instructions.md").read_text(encoding="utf-8")
        self.assertEqual(instructions.rstrip("\n"), legacy_agent["spec"]["systemPrompt"]["inline"])
        case = (WORKSPACE / "eval" / "fixed-greeting.yaml").read_text(encoding="utf-8")
        self.assertIn('input: "Reply with exactly: Hello world."', case)
        self.assertIn("pattern: '^Hello world\\.$'", case)

    def test_workspace_uses_the_reviewed_model_and_tool_free_orka_profile(self):
        member = (WORKSPACE / "agents" / "hello" / "member.yaml").read_text(encoding="utf-8")
        self.assertRegex(member, r"(?m)^\s+model: gpt-4\.1-mini$")
        self.assertRegex(member, r"(?m)^\s+id: orka$")
        profile = json.loads((WORKSPACE / "build-profiles" / "default.json").read_text(encoding="utf-8"))
        self.assertEqual(profile["id"], "agentkit-v0.1.0")

    def test_portable_evidence_and_reviewed_expectation_are_detached(self):
        self.assertFalse((WORKSPACE / "verification").exists())
        self.assertFalse((VERIFICATION / "suite-layout").exists())
        evidence = json.loads((VERIFICATION / "evidence.json").read_text(encoding="utf-8"))
        expected = json.loads((VERIFICATION / "expected.json").read_text(encoding="utf-8"))
        self.assertEqual(set(expected), {"subject", "execution", "evaluator", "judges"})
        self.assertEqual(expected["judges"], [])
        self.assertEqual(evidence["subject"], expected["subject"])
        self.assertEqual(evidence["execution"], expected["execution"])
        self.assertEqual(evidence["evaluator"]["identity"], expected["evaluator"])

    def test_evidence_covers_the_complete_passing_case(self):
        evidence = json.loads((VERIFICATION / "evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["schemaVersion"], "1.0.0")
        self.assertEqual(len(evidence["evaluation"]["cases"]), 1)
        self.assertEqual(evidence["evaluation"]["cases"][0]["id"], "fixed-greeting")
        self.assertEqual(evidence["evaluation"]["cases"][0]["runs"], 1)
        self.assertEqual(evidence["evaluation"]["cases"][0]["minPasses"], 1)
        self.assertEqual(evidence["results"][0]["outcome"], "pass")
        run = evidence["results"][0]["runs"][0]
        self.assertEqual((run["status"], run["outcome"]), ("completed", "pass"))
        self.assertEqual(
            run["assertions"],
            [{"id": "exact-result-text", "outcome": "pass", "type": "regex"}],
        )

    def test_expected_subject_pins_one_exact_suite_digest(self):
        expected = json.loads((VERIFICATION / "expected.json").read_text(encoding="utf-8"))
        digest = expected["subject"]["manifest"]["digest"]
        self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(expected["subject"]["platform"], {
            "os": "linux", "architecture": "amd64", "variant": ""
        })
        self.assertEqual(expected["execution"]["model"]["id"], "gpt-4.1-mini")
        self.assertEqual(expected["evaluator"]["id"], "kmx")
        self.assertTrue(re.fullmatch(r"v0\.8\.1-git-[0-9a-f]{40}", expected["evaluator"]["version"]))

    def test_legacy_projection_is_retained_only_for_coordinator_compatibility(self):
        for relative in (
            "dependencies.lock.yaml",
            "environments/trial/kustomization.yaml",
            "environments/production/kustomization.yaml",
            "eval/acceptance.md",
            "eval/cases/fixed-greeting.yaml",
            "memory/baseline-manifest.yaml",
            "resources/agent.yaml",
        ):
            self.assertTrue((HELLO / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()

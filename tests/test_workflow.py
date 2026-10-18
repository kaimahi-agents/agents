"""Security invariants for the offline pull-request workflow."""

import unittest
from pathlib import Path

_WORKFLOW = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "agent-gate.yaml")


class AgentGateWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self.text = _WORKFLOW.read_text(encoding="utf-8")

    def test_checkout_does_not_persist_the_read_only_token(self):
        checkout = self.text.split("- uses: actions/checkout@", 1)[1].split("- name:", 1)[0]
        self.assertIn("persist-credentials: false", checkout)

    def test_third_party_actions_are_pinned_to_reviewed_commits(self):
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", self.text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", self.text)

    def test_hello_uses_the_checksum_pinned_kmx_release(self):
        self.assertIn("KMX_VERSION: v0.8.1", self.text)
        self.assertIn(
            "KMX_LINUX_AMD64_SHA256: 7f2d02d4c22d222d91ece03a9214bbd10a3e43403b9c37965c51110ba74151fc",
            self.text,
        )
        self.assertIn("sha256sum --check", self.text)
        self.assertIn("timeout-minutes: 15", self.text)
        self.assertIn("--connect-timeout 15 --max-time 120", self.text)
        self.assertIn("--retry 3 --retry-delay 2 --retry-all-errors", self.text)
        self.assertNotIn("/releases/latest/", self.text)

    def test_hello_prepares_current_source_and_verifies_portable_evidence(self):
        hello_gate = self.text.split('if [ "$agent" = "hello" ]; then', 1)[1].split("continue", 1)[0]
        for expected in (
            "push \\",
            "--workspace agents/hello/workspace",
            "--unevaluated",
            "--to-layout",
            "eval verify \\",
            "--from-layout",
            "--evidence agents/hello/verification/evidence.json",
            "--expect agents/hello/verification/expected.json",
        ):
            self.assertIn(expected, hello_gate)
        self.assertNotIn("--to-context", hello_gate)
        self.assertNotIn("--inference", hello_gate)
        self.assertNotIn("kmx eval --", hello_gate)

    def test_hello_gate_checks_missing_and_mismatched_evidence(self):
        self.assertIn("missing evidence unexpectedly verified", self.text)
        self.assertIn("mismatched evidence unexpectedly verified", self.text)
        self.assertIn('"sha256:" + "0" * 64', self.text)

    def test_gate_source_changes_execute_the_hello_gate(self):
        for path in (
            ".github/workflows/agent-gate.yaml",
            "tests/test_workflow.py",
            "tests/test_hello_suite.py",
        ):
            self.assertIn(path, self.text)
        self.assertIn('agents="${agents:+$agents }hello"', self.text)

    def test_non_hello_agents_keep_the_legacy_gate(self):
        legacy = self.text.split("continue", 1)[1]
        self.assertIn('python3 tools/render "agents/$agent"', legacy)
        self.assertIn('python3 tools/verify "agents/$agent"', legacy)


if __name__ == "__main__":
    unittest.main()

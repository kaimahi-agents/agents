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


if __name__ == "__main__":
    unittest.main()

"""The rollout decision document states the approval and secret-scanning rules it actually has."""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import agentctl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
ROLLOUT = REPO_ROOT / "agents" / "dependabot-repair" / "decisions" / "rollout.md"


class RolloutDecisionTestCase(unittest.TestCase):
    def setUp(self):
        self.text = ROLLOUT.read_text(encoding="utf-8")
        self.normalized = re.sub(r"\s+", " ", self.text)

    def test_two_approvals_are_required_unconditionally(self):
        self.assertIn("two distinct, non-author approvals", self.normalized)
        self.assertIn("without exception", self.normalized)

    def test_no_lower_risk_classification_reduces_the_requirement(self):
        for phrase in ("one for prompt-only", "prompt-only changes", "for its classification"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.normalized)

    def test_a_code_owner_review_is_required(self):
        self.assertIn("at least one of them from a code owner", self.normalized)

    def test_mechanically_scored_policy_receipts_require_every_assertion_not_a_human_verdict(self):
        self.assertNotIn("human-verdict", self.normalized)
        self.assertIn("mechanically-scored acceptance policy", self.normalized)
        self.assertIn("missing-toolchain-v2", self.normalized)
        self.assertIn("there is no operator verdict to fall back on", self.normalized)
        self.assertIn("review context was recorded for it at the time", self.normalized)

    def test_secret_scanning_is_described_as_operator_discipline_plus_the_gate(self):
        # The local pre-push run is not automatically enforced; only the gate run is.
        self.assertIn("before pushing", self.normalized)
        self.assertIn("operator discipline rather than automatic enforcement", self.normalized)
        self.assertIn("TruffleHog", self.normalized)

    def test_the_document_makes_no_claim_this_repository_installs_a_hook(self):
        self.assertIn("Nothing in this repository installs a pre-push hook", self.normalized)


class NamespaceContractDocumentationTestCase(unittest.TestCase):
    def test_the_namespace_cross_check_documents_its_complete_behaviour(self):
        doc = re.sub(r"\s+", " ", agentctl.check_rendered_namespace.__doc__ or "")
        self.assertIn("at least one item to declare a namespace", doc)
        self.assertIn("every declared one to match exactly", doc)
        for command in ("eval", "deploy", "rollback-verify"):
            with self.subTest(command=command):
                self.assertIn(command, doc)


if __name__ == "__main__":
    unittest.main()

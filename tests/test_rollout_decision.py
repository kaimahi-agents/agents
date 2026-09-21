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
        promotion = self.text.split("## Promotion criteria", 1)[1].split("## ", 1)[0]
        self.promotion = re.sub(r"\s+", " ", promotion)

    def test_the_gate_is_required_but_reviews_are_not_yet_required(self):
        for phrase in ("required `agent-gate`", "Reviews are not yet required", "single maintainer"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.promotion)

    def test_obsolete_approval_requirements_are_absent(self):
        for phrase in ("two distinct, non-author approvals", "at least one of them from a code owner"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.promotion)

    def test_codeowners_routes_changes_without_being_an_approval_requirement(self):
        self.assertIn("`CODEOWNERS` still routes changes", self.promotion)
        self.assertIn("is not an approval requirement", self.promotion)

    def test_mechanically_scored_policy_receipts_require_every_assertion_not_a_human_verdict(self):
        self.assertNotIn("human-verdict", self.promotion)
        self.assertIn("mechanically-scored acceptance policy", self.promotion)
        self.assertIn("missing-toolchain-v2", self.promotion)
        self.assertIn("there is no operator verdict to fall back on", self.promotion)
        self.assertIn("review context was recorded for it at the time", self.promotion)

    def test_status_records_the_trial_promotion_and_rollback(self):
        self.assertIn("promoted to trial", self.normalized)
        self.assertIn("rolled back", self.normalized)

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

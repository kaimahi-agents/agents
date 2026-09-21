"""Useful guardrails for the short public README: size, links, facts, and privacy."""

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_README_PATH = _REPO_ROOT / "README.md"

_MAX_WORDS = 250

_REQUIRED_LINKS = (
    "https://github.com/Azure/k8s-lint/pull/239",
    "https://github.com/Azure/k8s-lint/pull/240",
    "https://github.com/orka-agents/orka/issues/485",
    "https://github.com/kaimahi-agents/agents/pull/2",
    "https://github.com/kaimahi-agents/agents/pull/3",
    "https://github.com/kaimahi-agents/agents/pull/4",
    "https://github.com/kaimahi-agents/agents/pull/7",
    "https://github.com/kaimahi-agents/agents/pull/6",
    "https://github.com/kaimahi-agents/agents/pull/8",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text)


class ReadmeTestCase(unittest.TestCase):
    def setUp(self):
        self.text = _README_PATH.read_text(encoding="utf-8")
        self.normalized = _normalize(self.text)

    def test_readme_exists(self):
        self.assertTrue(_README_PATH.is_file())

    def test_word_count_is_under_limit(self):
        word_count = len(self.text.split())
        self.assertLess(word_count, _MAX_WORDS, f"README is {word_count} words, must be under {_MAX_WORDS}")

    def test_required_facts_are_present_without_locking_full_sentences(self):
        for term in ("agents on AKS", "our own repos", "test bed", "day to day", "only runs when you tell it to",
                     "Automerge is off", "runtime has no credentials", "separate trusted component",
                     "fine publishing the prompt", "runtime image with a package manager",
                     "gated tool installation during repository validation"):
            with self.subTest(term=term):
                self.assertIn(term, self.normalized)

    def test_every_required_link_target_is_present(self):
        for link in _REQUIRED_LINKS:
            with self.subTest(link=link):
                self.assertIn(link, self.text)

    def test_gate_policy_is_stated_plainly(self):
        for term in ("passing test receipt for that exact version", "checks it offline", "never touches a cluster",
                     "one maintainer", "reviews aren't required", "Admins can't bypass the gate"):
            with self.subTest(term=term):
                self.assertIn(term, self.normalized)

    def test_pr_two_is_the_concrete_blocked_change_example(self):
        self.assertIn("looked fine", self.normalized)
        self.assertIn("36 requests against a limit of 10", self.normalized)

    def test_does_not_contain_a_local_or_internal_identifier_shape(self):
        # Any *specific* internal name (a person, a workstream ID, a local host path, an
        # experiment label) is the full-tree secret scanner's job -- see tools/agentctl.py's
        # `_VALUE_RULES`/`_LINE_RULES` and tests/test_secret_scan.py, which run over every
        # tracked file including this README. This test only pins the README against the
        # *shapes* of value that public policy forbids regardless of exact spelling, so it
        # stays meaningful even as internal names change.
        prohibited_patterns = (
            ("home-directory-path", re.compile(r"/(?:home|root|Users)/")),
            ("cluster-context-identifier", re.compile(r"\bkind-[a-z0-9-]+\b", re.IGNORECASE)),
            ("workstream-style-label", re.compile(r"\bw\d{2}\b", re.IGNORECASE)),
        )
        for name, pattern in prohibited_patterns:
            with self.subTest(pattern=name):
                self.assertIsNone(pattern.search(self.text), f"README matches prohibited shape {name!r}")

    def test_does_not_cite_the_local_unpublished_design_document(self):
        # DESIGN.md is a local planning document, never published to this
        # public repository; a reader-facing citation to it would be a
        # dangling reference.
        self.assertNotIn("DESIGN.md", self.text)

    def test_the_four_link_story_and_remaining_gaps_are_plain(self):
        for term in ("details Orka redacts", "limit what the agent can do", "Second try", "Passed in 4 requests",
                     "No retest needed", "Agents don't call other agents", "Memory isn't versioned",
                     "one test case"):
            with self.subTest(term=term):
                self.assertIn(term, self.normalized)


if __name__ == "__main__":
    unittest.main()

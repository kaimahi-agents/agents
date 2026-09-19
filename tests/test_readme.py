"""Regression tests for the top-level README.md: word count, the three
mandated concepts appearing exactly once each, and the required link
targets.

These are plain text checks -- no network access, no cluster, and no
dependency beyond the standard library.
"""

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_README_PATH = _REPO_ROOT / "README.md"

_MAX_WORDS = 300

# Each entry: a substring that must appear in the whitespace-normalized
# README text exactly once. Markdown line-wrapping means a literal
# substring can straddle a soft line break, so the text is normalized
# (all whitespace runs collapsed to a single space) before counting --
# this mirrors how the paragraph actually reads once rendered.
_REQUIRED_ONCE_PHRASES = (
    # Statement 1: this is an evaluation, not an operational process.
    "evaluation of running agents on AKS using our own repositories as realistic workloads",
    "not a team's operational process",
    # Statement 2: explicit command, automerge off, no credentials,
    # separate trusted publisher -- why the prompt can be published.
    "runs only on an explicit command",
    "automerge off",
    "no credentials in its runtime",
    "separate trusted component",
    # Statement 3: the repair needs a runtime image with a package manager.
    "needs a runtime image with a package manager",
)

_REQUIRED_LINKS = (
    "https://github.com/Azure/k8s-lint/pull/239",
    "https://github.com/Azure/k8s-lint/pull/240",
    "https://github.com/orka-agents/orka/issues/485",
    "https://github.com/kaimahi-agents/agents/pull/1",
    "https://github.com/kaimahi-agents/agents/pull/2",
    "https://github.com/kaimahi-agents/agents/pull/3",
    "https://github.com/kaimahi-agents/agents/pull/4",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text)


class ReadmeTestCase(unittest.TestCase):
    def setUp(self):
        self.text = _README_PATH.read_text(encoding="utf-8")
        self.normalized = _normalize(self.text)

    def test_readme_exists(self):
        self.assertTrue(_README_PATH.is_file())

    def test_word_count_is_under_300(self):
        word_count = len(self.text.split())
        self.assertLess(word_count, _MAX_WORDS, f"README is {word_count} words, must be under {_MAX_WORDS}")

    def test_each_mandated_phrase_appears_exactly_once(self):
        for phrase in _REQUIRED_ONCE_PHRASES:
            with self.subTest(phrase=phrase):
                count = self.normalized.count(phrase)
                self.assertEqual(count, 1, f"expected exactly one occurrence of {phrase!r}, found {count}")

    def test_every_required_link_target_is_present(self):
        for link in _REQUIRED_LINKS:
            with self.subTest(link=link):
                self.assertIn(link, self.text)

    def test_pr_four_link_is_the_highest_repository_pr_number_linked(self):
        # Pins the "predictable repository PR URLs 1-4" contract: exactly
        # four, no fifth speculative PR linked.
        self.assertNotIn("https://github.com/kaimahi-agents/agents/pull/5", self.text)

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

    def test_does_not_assert_an_outcome_for_prs_2_through_4_before_they_exist(self):
        # PRs 2-4 are not opened yet when this README is authored; it may
        # describe their *intended* purpose but must never assert that one
        # already merged, passed, or was blocked -- each PR's own state is
        # the actual record.
        lowered = self.normalized.lower()
        for outcome_word in ("merged", "passed", "blocked", "failed", "rolled back"):
            with self.subTest(outcome_word=outcome_word):
                self.assertNotIn(outcome_word, lowered)


if __name__ == "__main__":
    unittest.main()

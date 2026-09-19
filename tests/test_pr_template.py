"""Keep the pull-request template focused on one classification question."""

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATE_PATH = _REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"

_QUESTION_LINE_RE = re.compile(r"\?\s*$")
_CHECKBOX_LINE_RE = re.compile(r"^-\s*\[([ xX])\]\s*(.+?)\s*$")


class PullRequestTemplateTestCase(unittest.TestCase):
    def setUp(self):
        self.text = _TEMPLATE_PATH.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()

    def test_template_exists(self):
        self.assertTrue(_TEMPLATE_PATH.is_file())

    def test_exactly_one_question_line(self):
        question_lines = [line for line in self.lines if _QUESTION_LINE_RE.search(line)]
        self.assertEqual(len(question_lines), 1, f"expected exactly one question line, found {question_lines}")

    def test_exactly_two_checkbox_options(self):
        checkbox_lines = [line for line in self.lines if _CHECKBOX_LINE_RE.match(line)]
        self.assertEqual(len(checkbox_lines), 2, f"expected exactly two checkbox options, found {checkbox_lines}")

    def test_both_checkbox_options_start_unchecked(self):
        checkbox_lines = [_CHECKBOX_LINE_RE.match(line) for line in self.lines if _CHECKBOX_LINE_RE.match(line)]
        for match in checkbox_lines:
            with self.subTest(option=match.group(2)):
                self.assertEqual(match.group(1), " ", f"option {match.group(2)!r} must start unchecked")

    def test_checkbox_option_texts_are_distinct_and_non_empty(self):
        checkbox_lines = [_CHECKBOX_LINE_RE.match(line) for line in self.lines if _CHECKBOX_LINE_RE.match(line)]
        texts = [match.group(2) for match in checkbox_lines]
        self.assertEqual(len(texts), len(set(texts)), "checkbox option texts must be distinct")
        for text in texts:
            self.assertTrue(text.strip())


if __name__ == "__main__":
    unittest.main()

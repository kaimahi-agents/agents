"""Structural checks for the agent catalogue and its documentation."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
VERSIONING_DOC = ROOT / "docs" / "versioning-and-rollback.md"
AGENTS = ROOT / "agents"
ALLOWED_STATUSES = {
    "tested",
    "tested in simulation",
    "ran, no tests yet",
    "tested, ran on real PRs",
    "tested, trial red on report receipt",
}
LINK_RE = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
TOOL_COMMAND_RE = re.compile(r"^\s*(tools/[a-z0-9-]+)\b")
REPO_PR_RE = re.compile(r"https://github\.com/kaimahi-agents/agents/pull/(2|3|4|7)\b")


def markdown_files():
    files = [README]
    for directory in (".github", "agents", "docs", "tests", "tools"):
        root = ROOT / directory
        files += sorted(root.rglob("*.md")) if root.is_dir() else []
    return files


def catalogue_rows():
    rows = {}
    for line in README.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            continue
        match = re.fullmatch(r"\[([a-z0-9-]+)\]\(agents/\1/?\)", cells[0])
        if match:
            rows[match.group(1)] = cells[3]
    return rows


class CatalogueTestCase(unittest.TestCase):
    def test_catalogue_and_agent_directories_match(self):
        directories = {path.name for path in AGENTS.iterdir() if path.is_dir()}
        self.assertEqual(set(catalogue_rows()), directories)

    def test_catalogue_statuses_use_the_fixed_vocabulary(self):
        self.assertTrue(catalogue_rows())
        for agent, status in catalogue_rows().items():
            with self.subTest(agent=agent):
                self.assertIn(status, ALLOWED_STATUSES)

    def test_relative_markdown_links_resolve(self):
        for source in markdown_files():
            for target in LINK_RE.findall(source.read_text(encoding="utf-8")):
                target = target.split("#", 1)[0].split("?", 1)[0]
                if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                with self.subTest(source=source.relative_to(ROOT), target=target):
                    self.assertTrue((source.parent / target).resolve().exists())

    def test_coordinator_row_links_to_a_public_readme(self):
        rows = [line for line in README.read_text(encoding="utf-8").splitlines()
                if line.startswith("| [coordinator](agents/coordinator/)")]
        self.assertEqual(len(rows), 1)
        self.assertEqual(catalogue_rows().get("coordinator"), "tested, trial red on report receipt")
        self.assertTrue((ROOT / "agents" / "coordinator" / "README.md").is_file())

    def test_versioning_docs_have_one_pinned_composition_paragraph(self):
        paragraphs = [paragraph.strip() for paragraph in VERSIONING_DOC.read_text(encoding="utf-8").split("\n\n")
                      if paragraph.strip()]
        matching = [paragraph for paragraph in paragraphs if "catalogue/promotion pin" in paragraph]
        self.assertEqual(len(matching), 1)
        self.assertIn("reverse-dependent gate", matching[0])

    def test_public_docs_do_not_name_internal_workstreams(self):
        pattern = re.compile(r"\bw\d{2}\b", re.IGNORECASE)
        for source in markdown_files():
            with self.subTest(source=source.relative_to(ROOT)):
                self.assertIsNone(pattern.search(source.read_text(encoding="utf-8")))

    def test_documented_tools_exist_and_are_executable(self):
        commands = set()
        for source in markdown_files():
            commands.update(match.group(1) for line in source.read_text(encoding="utf-8").splitlines()
                            if (match := TOOL_COMMAND_RE.match(line)))
        self.assertTrue({"tools/render", "tools/verify"} <= commands)
        for command in commands:
            with self.subTest(command=command):
                path = ROOT / command
                self.assertTrue(path.is_file())
                self.assertTrue(path.stat().st_mode & 0o111)

    def test_worked_example_is_the_only_place_with_experiment_pr_links(self):
        occurrences = []
        for source in markdown_files():
            occurrences += [(source, number) for number in REPO_PR_RE.findall(source.read_text(encoding="utf-8"))]
        self.assertEqual([number for _, number in occurrences], ["2", "4", "3", "7"])
        self.assertTrue(all(source == ROOT / "docs" / "versioning-and-rollback.md" for source, _ in occurrences))


if __name__ == "__main__":
    unittest.main()

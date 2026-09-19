"""Changed-agent discovery: which directories a diff touches, and failing closed on unsafe ones."""

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import agentctl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


class DiscoverChangedAgentDirsTestCase(unittest.TestCase):
    def test_only_the_first_segment_under_agents_names_the_agent(self):
        self.assertEqual(agentctl.discover_changed_agent_dirs(
            ["agents/demo/prompts/system.md", "agents/demo/resources/agent.yaml"]), ["demo"])

    def test_results_are_sorted_and_deduplicated(self):
        self.assertEqual(agentctl.discover_changed_agent_dirs(
            ["agents/zeta/a.md", "agents/alpha/b.md", "agents/zeta/c.md"]), ["alpha", "zeta"])

    def test_paths_outside_agents_are_ignored(self):
        self.assertEqual(agentctl.discover_changed_agent_dirs(
            ["README.md", "tools/agentctl.py", ".github/workflows/agent-gate.yaml", ""]), [])

    def test_a_file_directly_under_agents_is_not_an_agent_directory(self):
        self.assertEqual(agentctl.discover_changed_agent_dirs(["agents/README.md", "agents/demo/"]), [])

    def test_surrounding_whitespace_is_tolerated(self):
        self.assertEqual(agentctl.discover_changed_agent_dirs(["  agents/demo/a.md  \n"]), ["demo"])

    def test_an_unsafe_segment_fails_closed_without_echoing_it(self):
        # Dropping it silently would let a real agent change pass the gate as an empty,
        # successful discovery.
        for path in ("agents/../etc/passwd/file", "agents/Demo Agent/a.md", "agents/-leading/a.md",
                     "agents/" + "a" * 100 + "/a.md"):
            with self.subTest(path=path), self.assertRaises(agentctl.CliError) as caught:
                agentctl.discover_changed_agent_dirs([path])
            self.assertIn("unsafe agent directory segment", str(caught.exception))
            self.assertNotIn("passwd", str(caught.exception))

    def test_one_unsafe_path_fails_the_whole_batch(self):
        with self.assertRaises(agentctl.CliError):
            agentctl.discover_changed_agent_dirs(["agents/demo/a.md", "agents/Bad Name/b.md"])


class DiscoverCliTestCase(unittest.TestCase):
    def run_cli(self, stdin_text):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(stdin_text)), \
                redirect_stdout(out), redirect_stderr(err):
            code = agentctl.main_discover_changed_agents([])
        return code, out.getvalue(), err.getvalue()

    def test_names_are_printed_one_per_line(self):
        code, out, _ = self.run_cli("agents/demo/a.md\nagents/other/b.md\n")
        self.assertEqual((code, out), (0, "demo\nother\n"))

    def test_an_unsafe_path_exits_nonzero_and_prints_no_names(self):
        code, out, err = self.run_cli("agents/../etc/passwd/file\n")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertNotIn("passwd", err)
        self.assertNotIn("Traceback", err)

    def test_the_shipped_wrapper_exits_nonzero_on_an_unsafe_path(self):
        # The gate pipes `git diff --name-only` into this wrapper and relies on its exit code.
        completed = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "discover-changed-agents")],
                                   input="agents/../etc/passwd/file\n", capture_output=True, text=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn("passwd", completed.stdout + completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()

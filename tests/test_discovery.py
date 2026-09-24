"""Changed-agent discovery: path parsing plus catalogue reverse-dependency expansion."""

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures import write_json, write_native_agent, write_native_coordinator  # noqa: E402
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


class CatalogueGraphTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "agents").mkdir()

    def init_git_repo(self):
        for command in (
            ["git", "init"],
            ["git", "config", "user.name", "Test User"],
            ["git", "config", "user.email", "test@example.com"],
        ):
            completed = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def commit_all(self, message="test commit"):
        for command in (["git", "add", "."], ["git", "commit", "-m", message]):
            completed = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def write_native(self, slug, *, agent_name="hello") -> Path:
        return write_native_agent(self.root / "agents" / slug, namespace="orka-system",
                                  agent_name=agent_name, provider_name=agent_name)

    def write_coordinator(self, slug="coordinator", *, agent_name="coordinator", allowed_agents=("hello",),
                          catalogue_agents=None) -> Path:
        return write_native_coordinator(self.root / "agents" / slug, namespace="orka-system",
                                        agent_name=agent_name, allowed_agents=allowed_agents,
                                        catalogue_agents=catalogue_agents)

    def test_load_catalogue_graph_maps_resource_names_to_directory_slugs(self):
        self.write_native("hello-child", agent_name="hello")
        self.write_coordinator(catalogue_agents={"hello": {"trial": "a" * 64, "production": "b" * 64}})
        graph = agentctl.load_catalogue_graph(self.root)
        self.assertEqual(graph.name_to_dir["hello"], "hello-child")
        self.assertEqual(list(graph.reverse["hello-child"]), ["coordinator"])

    def test_expand_changed_agent_dirs_includes_transitive_reverse_dependencies_from_head_tree(self):
        self.write_native("hello")
        self.write_coordinator(catalogue_agents={"hello": {"trial": "a" * 64, "production": "b" * 64}})
        self.write_coordinator(slug="root", agent_name="root", allowed_agents=("coordinator",),
                               catalogue_agents={"coordinator": {"trial": "c" * 64, "production": "d" * 64}})
        self.assertEqual(agentctl.expand_changed_agent_dirs(
            self.root, ["agents/hello/resources/agent.yaml"]), ["coordinator", "hello", "root"])

    def test_directory_names_may_differ_from_agent_resource_names(self):
        self.write_native("hello-child", agent_name="hello")
        self.write_coordinator(catalogue_agents={"hello": {"trial": "a" * 64, "production": "b" * 64}})
        self.assertEqual(agentctl.expand_changed_agent_dirs(
            self.root, ["agents/hello-child/resources/agent.yaml", "agents/hello-child/prompts/extra.md"]),
            ["coordinator", "hello-child"])

    def test_expansion_results_are_sorted_and_deduplicated(self):
        self.write_native("hello")
        self.write_coordinator(catalogue_agents={"hello": {"trial": "a" * 64, "production": "b" * 64}})
        self.assertEqual(agentctl.expand_changed_agent_dirs(
            self.root,
            ["agents/hello/resources/agent.yaml", "agents/coordinator/resources/agent.yaml",
             "agents/hello/prompts/system.md", "agents/coordinator/eval/acceptance.md"]),
            ["coordinator", "hello"])

    def test_duplicate_agent_resource_names_fail_closed(self):
        self.write_native("hello-one", agent_name="hello")
        self.write_native("hello-two", agent_name="hello")
        with self.assertRaises(agentctl.CliError):
            agentctl.load_catalogue_graph(self.root)

    def test_catalogue_dependency_cycles_fail_closed(self):
        self.write_coordinator(slug="alpha", agent_name="alpha", allowed_agents=("bravo",),
                               catalogue_agents={"bravo": {"trial": "a" * 64, "production": "b" * 64}})
        self.write_coordinator(slug="bravo", agent_name="bravo", allowed_agents=("alpha",),
                               catalogue_agents={"alpha": {"trial": "c" * 64, "production": "d" * 64}})
        with self.assertRaises(agentctl.CliError):
            agentctl.load_catalogue_graph(self.root)

    def test_unknown_catalogue_children_fail_closed(self):
        self.write_coordinator(catalogue_agents={"hello": {"trial": "a" * 64, "production": "b" * 64}})
        with self.assertRaises(agentctl.CliError):
            agentctl.load_catalogue_graph(self.root)

    def test_malformed_unrelated_lock_fails_closed(self):
        self.write_native("hello")
        self.write_coordinator(catalogue_agents={"hello": {"trial": "a" * 64, "production": "b" * 64}})
        self.write_native("other", agent_name="other")
        write_json(self.root / "agents" / "other" / "dependencies.lock.yaml",
                   {"catalogueAgents": {"hello": {"trial": "a" * 64}}})
        with self.assertRaises(agentctl.CliError):
            agentctl.expand_changed_agent_dirs(self.root, ["agents/hello/resources/agent.yaml"])

    def test_unsafe_catalogue_names_are_rejected_without_echoing_them(self):
        self.write_native("hello")
        self.write_coordinator(allowed_agents=("../../etc/passwd",),
                               catalogue_agents={"../../etc/passwd": {"trial": "a" * 64,
                                                                        "production": "b" * 64}})
        with self.assertRaises(agentctl.CliError) as caught:
            agentctl.load_catalogue_graph(self.root)
        self.assertIn("safe slug", str(caught.exception))
        self.assertNotIn("passwd", str(caught.exception))

    def test_missing_catalogue_pins_fail_closed(self):
        self.write_native("hello")
        self.write_coordinator(catalogue_agents={"hello": {"trial": "a" * 64}})
        with self.assertRaises(agentctl.CliError):
            agentctl.load_catalogue_graph(self.root)

    def test_ignored_and_untracked_safe_agent_dirs_do_not_affect_the_graph(self):
        self.init_git_repo()
        self.write_native("hello")
        self.write_coordinator(catalogue_agents={"hello": {"trial": "a" * 64, "production": "b" * 64}})
        (self.root / ".gitignore").write_text("agents/ignored/\n", encoding="utf-8")
        self.commit_all("baseline")
        for slug in ("ignored", "untracked"):
            with self.subTest(slug=slug):
                write_native_agent(self.root / "agents" / slug, agent_name="hello", provider_name="hello")
                self.assertEqual(agentctl.expand_changed_agent_dirs(
                    self.root, ["agents/hello/resources/agent.yaml"]), ["coordinator", "hello"])


class DiscoverCliTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "agents").mkdir()

    def run_cli(self, stdin_text, argv=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(stdin_text)), \
                redirect_stdout(out), redirect_stderr(err):
            code = agentctl.main_discover_changed_agents(list(argv or []))
        return code, out.getvalue(), err.getvalue()

    def test_names_are_printed_one_per_line(self):
        write_native_agent(self.root / "agents" / "demo", agent_name="demo", provider_name="demo")
        write_native_agent(self.root / "agents" / "other", agent_name="other", provider_name="other")
        code, out, _ = self.run_cli("agents/demo/a.md\nagents/other/b.md\n", ["--root", str(self.root)])
        self.assertEqual((code, out), (0, "demo\nother\n"))

    def test_cli_uses_the_checked_out_head_tree_for_reverse_expansion(self):
        hello = write_native_agent(self.root / "agents" / "hello", namespace="orka-system")
        write_native_coordinator(self.root / "agents" / "coordinator", namespace="orka-system",
                                 catalogue_agents={
                                     "hello": {
                                         "trial": agentctl.render_agent(
                                             hello, "trial", self.root / "hello-trial.json")["bundle_digest"],
                                         "production": agentctl.render_agent(
                                             hello, "production", self.root / "hello-production.json")["bundle_digest"],
                                     }
                                 })
        code, out, _ = self.run_cli("agents/hello/resources/agent.yaml\n", ["--root", str(self.root)])
        self.assertEqual((code, out), (0, "coordinator\nhello\n"))

    def test_an_unsafe_path_exits_nonzero_and_prints_no_names(self):
        code, out, err = self.run_cli("agents/../etc/passwd/file\n", ["--root", str(self.root)])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertNotIn("passwd", err)
        self.assertNotIn("Traceback", err)

    def test_the_shipped_wrapper_exits_nonzero_on_an_unsafe_path(self):
        # The gate pipes `git diff --name-only` into this wrapper and relies on its exit code.
        completed = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "discover-changed-agents")],
                                   cwd=self.root, input="agents/../etc/passwd/file\n",
                                   capture_output=True, text=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn("passwd", completed.stdout + completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()

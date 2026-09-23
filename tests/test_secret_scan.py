"""The bounded public-tree secret scanner: rule coverage, fail-closed discovery, no value leaks.

Every sample below is assembled from fragments so this file is never itself a finding; the
repository self-scan at the end of this module is the check that keeps that honest.
"""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import agentctl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
HOME_PATH = "/" + "home/someone/notes.txt"
CONTEXT_NAME = "kind-" + "example-test"
KUBECONFIG_FLAG = "--kube" + "config /tmp/cluster.yaml"

SAMPLES = (
    ("private-key-material", "-----BEGIN " + "RSA PRIVATE KEY-----"),
    ("github-token", "token: " + "ghp_" + "A" * 24),
    ("aws-access-key-id", "id = " + "AKIA" + "ABCDEFGHIJKLMNOP"),
    ("bearer-token", "Authorization: " + "Bearer " + "abcdefgh12345678"),
    ("home-directory-path", f"evidence at {HOME_PATH}"),
    ("windows-local-path", "path: C:" + chr(92) + "Users" + chr(92) + "someone"),
    ("cluster-context-identifier", f"context: {CONTEXT_NAME}"),
    ("container-registry-host", "image: " + "myregistry" + ".azurecr.io/agent:v1"),
    ("kubeconfig-reference", KUBECONFIG_FLAG),
)


class ScanLineTestCase(unittest.TestCase):
    def test_every_rule_matches_its_sample(self):
        for rule_id, sample in SAMPLES:
            with self.subTest(rule_id=rule_id):
                self.assertIn(rule_id, agentctl.scan_line(sample))

    def test_ordinary_technical_prose_is_not_flagged(self):
        for line in ("write evidence under /tmp/evidence and /var/log", "read /etc/hosts and /usr/share/doc",
                     "this workaround is somewhat kind-of a hack", "the kubeconfig flag is always explicit",
                     "def run(context, kubeconfig, args):", "parser.add_argument(\"--kube\" + \"config\")",
                     "image: registry.example.com/agent:v1", "kind: RepositoryMonitor"):
            with self.subTest(line=line):
                self.assertEqual(agentctl.scan_line(line), [])

    def test_document_scan_detects_a_windows_path_after_json_escaping(self):
        # Regression: json.dumps escapes a literal backslash to two backslashes, so a document
        # value with one real backslash (as any in-memory Windows path would have) reaches the
        # scanned text as two -- a rule pinned to exactly one backslash would silently stop
        # matching once the value is serialized, even though `scan_line` still catches it in a
        # plain-text file that already contains the doubled, JSON-escaped form.
        windows_path = "C:" + chr(92) + "Users" + chr(92) + "someone"
        findings = agentctl.find_prohibited_in_document({"note": windows_path}, "receipt")
        self.assertTrue(any("windows-local-path" in finding for finding in findings), findings)

    def test_kind_context_parity_between_line_and_document_scans(self):
        # Finding 2: the value rules and the line rules share one cluster-context pattern, so a
        # benign English compound is not a finding in either scan and a real context is in both.
        benign = "this is kind-of expected"
        self.assertEqual(agentctl.scan_line(benign), [])
        self.assertEqual(agentctl.find_prohibited_in_document({"note": benign}, "receipt"), [])
        self.assertIn("cluster-context-identifier", agentctl.scan_line(CONTEXT_NAME))
        self.assertTrue(agentctl.find_prohibited_in_document({"note": CONTEXT_NAME}, "receipt"))


class CredentialAssignmentTestCase(unittest.TestCase):
    # Each sample is a (prefix, rest) pair so no physical line in this file begins with a
    # `key = value` shape the scanner would itself flag.
    FLAGGED = (("client_", 'secret = "s3cr3t-value-here"'),
               ("api_", 'key: "AKfycbx-not-a-placeholder"'),
               ("  access_", "token = 'abc123def456ghi'"))
    EXEMPT = (("client_", 'secret = "changeme"'), ("api_", "key: ${SECRET_FROM_VAULT}"),
              ("api_", "key: {{ vault_lookup }}"), ("access_", "token = <redacted>"),
              ("client_", "secret = null"), ("api_", "key = read_token_file(path)"),
              ("api_", "key = os.environ.get('API_KEY')"))

    def test_a_literal_credential_value_is_flagged(self):
        for prefix, rest in self.FLAGGED:
            with self.subTest(rest=rest):
                self.assertIn("credential-assignment", agentctl.scan_line(prefix + rest))

    def test_placeholders_indirection_and_call_expressions_are_exempt(self):
        for prefix, rest in self.EXEMPT:
            with self.subTest(rest=rest):
                self.assertEqual(agentctl.scan_line(prefix + rest), [])

    def test_only_exact_structural_secret_ref_openings_are_exempt(self):
        lines = ('"secret' + 'Ref": {', 'secret' + 'Ref: [', 'secret' + 'Ref: {   ', 'secret' + 'Ref: [,')
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(agentctl.scan_line(line), [])

    def test_inline_secret_ref_objects_and_arrays_still_flag(self):
        lines = ('secret' + 'Ref: {name: provider-key}', 'secret' + 'Ref: {"value":"real-secret"}',
                 'secret' + 'Ref = ["external"]')
        for line in lines:
            with self.subTest(line=line):
                self.assertIn("credential-assignment", agentctl.scan_line(line))

    def test_structural_secret_ref_exemption_does_not_exempt_other_sensitive_keys(self):
        self.assertIn("credential-assignment", agentctl.scan_line('api_' + 'key: {"value": "abc123"}'))
        self.assertIn("credential-assignment", agentctl.scan_line('access_' + 'token: ["abc123"]'))

    def test_only_an_exact_call_expression_is_exempt(self):
        # Finding 6: a value that merely contains parentheses is still a credential, whereas a
        # value that is entirely a call expression is code, not a literal secret.
        for prefix, rest in (("client_", 'secret = "s3cr3t(value)-here"'),
                             ("client_", 'secret = "abc" + lookup()'),
                             ("api_", 'key = os.environ["API_KEY"]')):
            with self.subTest(rest=rest):
                self.assertIn("credential-assignment", agentctl.scan_line(prefix + rest))


class ScanFileTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_findings_carry_path_line_and_rule_but_never_the_value(self):
        (self.root / "notes.md").write_text(f"one\ntwo\n{HOME_PATH}\n", encoding="utf-8")
        findings = agentctl.scan_file(self.root, "notes.md")
        self.assertEqual(findings, [("notes.md", 3, "home-directory-path")])
        self.assertNotIn(HOME_PATH, str(findings))

    def test_binary_and_oversized_files_are_skipped(self):
        (self.root / "blob.bin").write_bytes(b"\x00" + HOME_PATH.encode("utf-8"))
        self.assertEqual(agentctl.scan_file(self.root, "blob.bin"), [])
        (self.root / "big.txt").write_bytes(b"x" * (agentctl.MAX_SCAN_BYTES + 1) + HOME_PATH.encode("utf-8"))
        self.assertEqual(agentctl.scan_file(self.root, "big.txt"), [])

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can read any file")
    def test_an_unreadable_file_fails_closed(self):
        # Finding 7: silently skipping an unreadable file would report a clean tree.
        target = self.root / "locked.txt"
        target.write_text("content\n", encoding="utf-8")
        target.chmod(0o000)
        self.addCleanup(target.chmod, 0o600)
        with self.assertRaises(agentctl.CliError):
            agentctl.scan_file(self.root, "locked.txt")


class DiscoveryTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, check=True)

    def test_gitignored_and_git_internal_paths_are_skipped(self):
        self.git("init", "-q")
        (self.root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        (self.root / "tracked.txt").write_text("ok\n", encoding="utf-8")
        (self.root / "ignored.txt").write_text(HOME_PATH + "\n", encoding="utf-8")
        candidates = agentctl.iter_candidate_files(self.root)
        self.assertIn("tracked.txt", candidates)
        self.assertNotIn("ignored.txt", candidates)
        self.assertFalse([path for path in candidates if path.startswith(".git/")])

    def test_symlinks_are_never_scanned(self):
        self.git("init", "-q")
        (self.root / "real.txt").write_text("ok\n", encoding="utf-8")
        (self.root / "link.txt").symlink_to(self.root / "real.txt")
        self.assertNotIn("link.txt", agentctl.iter_candidate_files(self.root))

    def test_a_git_discovery_failure_inside_a_work_tree_fails_closed(self):
        # Finding 7: degrading to an unfiltered walk here would silently change what is scanned.
        self.git("init", "-q")
        (self.root / "a.txt").write_text("ok\n", encoding="utf-8")
        (self.root / ".git" / "index").write_bytes(b"not-a-git-index")
        with self.assertRaises(agentctl.CliError):
            agentctl.iter_candidate_files(self.root)

    def test_a_plain_directory_still_scans_without_git(self):
        (self.root / "a.txt").write_text("ok\n", encoding="utf-8")
        self.assertEqual(agentctl.iter_candidate_files(self.root), ["a.txt"])


class SecretScanCliTestCase(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = agentctl.main_secret_scan(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_a_finding_exits_nonzero_and_reports_position_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "leak.txt").write_text(HOME_PATH + "\n", encoding="utf-8")
            code, _, err = self.run_cli(tmp)
        self.assertEqual(code, 1)
        self.assertIn("leak.txt:1: home-directory-path", err)
        self.assertNotIn(HOME_PATH, err)

    def test_this_repository_scans_clean(self):
        # Also proves this test module introduces no synthetic self-matches.
        code, out, err = self.run_cli(str(REPO_ROOT))
        self.assertEqual(code, 0, err)
        self.assertIn("secret-scan: ok", out)


if __name__ == "__main__":
    unittest.main()

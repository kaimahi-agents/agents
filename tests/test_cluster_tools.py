"""Cluster-touching commands: eval, deploy and rollback-verify, driven through fake seams.

`subprocess.run` and `http_get_json` are the only two ways this module reaches outside the
process, so every test here replaces exactly those and exercises the real argv construction,
JSON handling, guards and receipt building.
"""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures import RUNTIME_DIGEST, write_agent, write_json  # noqa: E402
from tools import agentctl  # noqa: E402

NAMESPACE = "trial-namespace"
TASK_NAME = "demo-task"
RUNTIME_IMAGE = "registry.example.com/agent@" + RUNTIME_DIGEST
TERMINAL_TASK = {"metadata": {"name": TASK_NAME}, "status": {"phase": "Succeeded",
                 "startTime": "2026-09-17T10:00:00.123456789Z", "completionTime": "2026-09-17T10:05:00Z"}}


def provider_rows(count, minute="01"):
    return [{"time": f"2026-09-17T10:{minute}:0{index}Z", "method": "POST", "path": "/v1/messages"}
            for index in range(count)]


class FakeKubectl:
    """Stands in for `subprocess.run`, keyed by the kubectl verb and target."""

    def __init__(self, responses=None, failures=()):
        self.responses = responses or {}
        self.failures = set(failures)
        self.calls = []

    def key(self, argv):
        rest = argv[5:]
        if rest[0] == "get" and len(rest) > 2 and not rest[2].startswith("-"):
            return (rest[1], rest[2])
        return (rest[1],) if rest[0] == "get" else (rest[0],)

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        key = self.key(argv)
        if key in self.failures:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="not found")
        payload = self.responses.get(key, {})
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(payload), stderr="")

    def verbs(self):
        return [argv[5] for argv, _ in self.calls]


class ClusterPrimitivesTestCase(unittest.TestCase):
    def test_both_selectors_are_required_before_any_subprocess(self):
        with mock.patch.object(agentctl.subprocess, "run") as runner:
            for context, kubeconfig in ((None, "file"), ("ctx", None), ("", "file"), ("ctx", "")):
                with self.subTest(context=context), self.assertRaises(agentctl.CliError):
                    agentctl.run_kubectl(context, kubeconfig, ["get", "pods"])
        runner.assert_not_called()

    def test_both_selectors_are_passed_explicitly(self):
        fake = FakeKubectl()
        with mock.patch.object(agentctl.subprocess, "run", fake):
            agentctl.run_kubectl_json("ctx", "cred-file", ["get", "task", TASK_NAME, "-n", NAMESPACE])
        argv = fake.calls[0][0]
        self.assertEqual(argv[:5], ["kubectl", "--context", "ctx", "--kubeconfig", "cred-file"])
        self.assertEqual(argv[-2:], ["-o", "json"])

    def test_a_kubectl_failure_reports_only_the_exit_code(self):
        failing = FakeKubectl(failures=[("task", TASK_NAME)])
        with mock.patch.object(agentctl.subprocess, "run", failing), self.assertRaises(agentctl.KubectlError) as caught:
            agentctl.run_kubectl_json("ctx", "cred", ["get", "task", TASK_NAME, "-n", NAMESPACE])
        self.assertNotIn("not found", str(caught.exception))

    def test_transport_policy_allows_https_and_loopback_http_only(self):
        for url in ("https://api.example.com/v1", "http://127.0.0.1:8080/v1", "http://localhost:8080/v1",
                    "http://[::1]:8080/v1"):
            with self.subTest(url=url):
                self.assertEqual(agentctl.check_url_transport_is_safe(url), [])
        for url in ("http://api.example.com/v1", "ftp://api.example.com", "://malformed", "http://10.0.0.5/v1"):
            with self.subTest(url=url):
                self.assertTrue(agentctl.check_url_transport_is_safe(url))

    def test_an_unsafe_transport_is_refused_before_connecting(self):
        with self.assertRaises(agentctl.HttpError):
            agentctl.http_get_json("http://api.example.com/v1", token="secret-token")

    def test_redirects_are_never_followed(self):
        handler = agentctl._NoRedirectHandler()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example.com"))

    def test_namespace_cross_check_requires_a_declared_and_matching_namespace(self):
        matching = {"items": [{"metadata": {"namespace": NAMESPACE}}, {"metadata": {}}]}
        self.assertEqual(agentctl.check_rendered_namespace(matching, NAMESPACE), [])
        for bundle in ({"items": [{"metadata": {}}]}, {"items": []},
                       {"items": [{"metadata": {"namespace": "other"}}]},
                       {"items": [{"metadata": {"namespace": NAMESPACE}}, {"metadata": {"namespace": "other"}}]}):
            with self.subTest(bundle=bundle):
                self.assertEqual(agentctl.check_rendered_namespace(bundle, NAMESPACE),
                                 [agentctl.NAMESPACE_MISMATCH_MESSAGE])

    def test_the_namespace_diagnostic_never_echoes_either_namespace(self):
        message = agentctl.check_rendered_namespace({"items": [{"metadata": {"namespace": "secret-ns"}}]}, NAMESPACE)[0]
        self.assertNotIn("secret-ns", message)
        self.assertNotIn(NAMESPACE, message)


class EvaluationMechanicsTestCase(unittest.TestCase):
    def test_journal_completeness_requires_full_contiguous_coverage(self):
        events = [{"seq": 1}, {"seq": 2}, {"seq": 3}]
        self.assertEqual(agentctl.check_journal_completeness(events, 3), [])
        self.assertEqual(agentctl.check_journal_completeness(list(reversed(events)), 3), [])
        self.assertTrue(agentctl.check_journal_completeness([{"seq": 1}, {"seq": 3}], 3))
        self.assertTrue(agentctl.check_journal_completeness([{"seq": 1}, {"seq": 1}, {"seq": 2}], 2))
        self.assertTrue(agentctl.check_journal_completeness([{"seq": 1}, {"seq": 9}], 2))
        self.assertTrue(agentctl.check_journal_completeness([{"noseq": 1}], 1))

    def test_paging_follows_the_after_cursor_and_sends_the_token_as_a_header(self):
        pages = [{"events": [{"seq": 1}, {"seq": 2}], "latestSeq": 4},
                 {"events": [{"seq": 3}, {"seq": 4}], "latestSeq": 4}]
        seen = []

        def fake_get(url, *, token=None, **kwargs):
            seen.append((url, token))
            return pages[len(seen) - 1]

        with mock.patch.object(agentctl, "http_get_json", fake_get):
            events, latest = agentctl.page_journal("https://api.example.com", TASK_NAME, NAMESPACE, token="tok")
        self.assertEqual([event["seq"] for event in events], [1, 2, 3, 4])
        self.assertEqual(latest, 4)
        self.assertIn("after=0", seen[0][0])
        self.assertIn("after=2", seen[1][0])
        self.assertNotIn("afterSeq", seen[1][0])
        self.assertNotIn("tok", seen[1][0])
        self.assertEqual({token for _, token in seen}, {"tok"})

    def test_paging_fails_closed_when_the_server_never_converges(self):
        with mock.patch.object(agentctl, "http_get_json", lambda *a, **k: {"events": [{"seq": 1}], "latestSeq": 99}), \
                self.assertRaises(agentctl.CliError):
            agentctl.page_journal("https://api.example.com", TASK_NAME, NAMESPACE, max_pages=3)

    def test_only_provider_post_rows_are_counted(self):
        rows = agentctl.parse_provider_log(json.dumps([
            {"time": "t", "method": "POST", "path": "/v1/messages"},
            {"time": "t", "method": "GET", "path": "/v1/messages"},
            {"time": "t", "method": "POST", "path": "/healthz"}]))
        self.assertEqual(len(rows), 1)

    def test_json_lines_logs_parse_and_reject_malformed_lines(self):
        text = "\n".join([json.dumps({"time": "t", "method": "POST", "path": "/v1/messages"}), "{not json",
                          json.dumps({"time": "t", "method": "POST", "path": "/v1/messages"})])
        with self.assertRaises(agentctl.CliError):
            agentctl.parse_provider_log(text)

    def test_malformed_json_array_never_falls_back_to_partial_json_lines(self):
        text = '[{"time":"t","method":"POST","path":"/v1/messages"},\n{bad}]'
        with self.assertRaises(agentctl.CliError):
            agentctl.parse_provider_log(text)

    def test_the_count_is_restricted_to_the_asserted_window(self):
        records = provider_rows(3, minute="01") + provider_rows(2, minute="30")
        start, end = agentctl.parse_timestamp("2026-09-17T10:00:00Z"), agentctl.parse_timestamp("2026-09-17T10:05:00Z")
        self.assertEqual(agentctl.count_provider_requests_in_window(records, start, end), 3)

    def test_a_record_without_a_timestamp_fails_closed(self):
        start, end = agentctl.parse_timestamp("2026-09-17T10:00:00Z"), agentctl.parse_timestamp("2026-09-17T10:05:00Z")
        with self.assertRaises(agentctl.CliError):
            agentctl.count_provider_requests_in_window([{"method": "POST", "path": "/v1/messages"}], start, end)

    def test_window_coverage_is_exact(self):
        task_start, task_end = agentctl.parse_timestamp("2026-09-17T10:00:00Z"), agentctl.parse_timestamp(
            "2026-09-17T10:05:00Z")
        self.assertEqual(agentctl.check_window_covers_task(task_start, task_end, task_start, task_end), [])
        late = agentctl.parse_timestamp("2026-09-17T10:00:01Z")
        self.assertTrue(agentctl.check_window_covers_task(late, task_end, task_start, task_end))
        early = agentctl.parse_timestamp("2026-09-17T10:04:59Z")
        self.assertTrue(agentctl.check_window_covers_task(task_start, early, task_start, task_end))

    def test_nanosecond_timestamps_parse_without_rounding(self):
        parsed = agentctl.parse_timestamp("2026-09-17T10:00:00.123456789Z")
        self.assertEqual(parsed.microsecond, 123456)

    def test_zero_retries_must_be_declared_explicitly(self):
        self.assertEqual(agentctl.check_zero_retries({"spec": {"maxRetries": 0}}), [])
        for spec in ({}, {"maxRetries": 1}, {"retries": 2}):
            with self.subTest(spec=spec):
                self.assertTrue(agentctl.check_zero_retries({"spec": spec}))

    def test_any_other_non_terminal_task_breaks_the_exclusive_window(self):
        reserved = {"name": TASK_NAME, "namespace": NAMESPACE, "phase": "Running"}
        self.assertEqual(agentctl.check_single_task_reservation(
            [{"name": "other", "namespace": "elsewhere", "phase": "Succeeded"}, reserved],
            TASK_NAME, NAMESPACE), [])
        for conflicting in ({"name": "other", "namespace": "elsewhere", "phase": "Running"},
                            {"name": TASK_NAME, "namespace": "elsewhere", "phase": "Running"}):
            with self.subTest(conflicting=conflicting):
                self.assertTrue(agentctl.check_single_task_reservation(
                    [reserved, conflicting], TASK_NAME, NAMESPACE))

    def test_redaction_and_omission_markers_are_both_detected(self):
        events = [{"seq": 1, "payload": agentctl.REDACTION_MARKER}, {"seq": 2, "tool": {"metadataOmitted": "policy"}},
                  {"seq": 3, "payload": "fine"}]
        self.assertEqual(agentctl.find_redacted_sequences(events), [1, 2])

    def test_polling_sleeps_for_real_between_attempts(self):
        # Finding 3: the default must be a genuine wait, not a no-op that burns the poll budget.
        states = [{"status": {"phase": "Running"}}, {"status": {"phase": "Succeeded"}}]
        with mock.patch.object(agentctl.time, "sleep") as sleeper:
            agentctl.wait_for_terminal(lambda: states.pop(0), poll_interval_seconds=7.0)
        sleeper.assert_called_once_with(7.0)

    def test_polling_fails_closed_after_the_attempt_budget(self):
        with mock.patch.object(agentctl.time, "sleep"), self.assertRaises(agentctl.CliError):
            agentctl.wait_for_terminal(lambda: {"status": {"phase": "Running"}}, max_attempts=2)


class EvalCliTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.agent = write_agent(self.root / "agent", namespace=NAMESPACE)
        self.evidence = self.root / "evidence"
        write_json(self.root / "task.json", {"apiVersion": "core.orka.ai/v1", "kind": "Task",
                                             "metadata": {"name": TASK_NAME}, "spec": {"maxRetries": 0}})
        (self.root / "token").write_text("journal-token\n", encoding="utf-8")
        (self.root / "provider.log").write_text(json.dumps(provider_rows(2)), encoding="utf-8")
        self.kubectl = FakeKubectl({("tasks.core.orka.ai",): {"items": []}, ("task", TASK_NAME): TERMINAL_TASK})
        self.pages = [{"events": [{"seq": 1}, {"seq": 2}], "latestSeq": 2}]

    def argv(self, **overrides):
        args = {"--context": "ctx", "--kubeconfig": "cred", "--evidence-root": str(self.evidence),
                "--agent-dir": str(self.agent), "--environment": "trial", "--namespace": NAMESPACE,
                "--date": "2026-09-17", "--case-id": "demo-case", "--model": "test-model",
                "--task-manifest": str(self.root / "task.json"), "--journal-base-url": "https://api.example.com",
                "--journal-token-file": str(self.root / "token"), "--provider-log": str(self.root / "provider.log"),
                "--window-start": "2026-09-17T09:59:00Z", "--window-end": "2026-09-17T10:06:00Z",
                "--max-provider-requests": "5", "--human-verdict": "pass"}
        args.update(overrides)
        return [token for flag, value in args.items() for token in (flag, value)]

    def run_eval(self, **overrides):
        queue = list(self.pages)

        def fetch(*args, **kwargs):
            return queue.pop(0) if queue else {"events": [], "latestSeq": self.pages[-1].get("latestSeq")}

        with mock.patch.object(agentctl.subprocess, "run", self.kubectl), \
                mock.patch.object(agentctl, "http_get_json", fetch), \
                redirect_stdout(io.StringIO()) as out:
            agentctl._eval_cli(self.argv(**overrides))
        return json.loads(out.getvalue())

    def receipt(self):
        written = sorted((self.agent / "eval" / "receipts").rglob("*.json"))
        self.assertEqual(len(written), 1)
        return json.loads(written[0].read_text(encoding="utf-8"))

    def test_a_complete_run_writes_a_schema_valid_public_safe_receipt(self):
        summary = self.run_eval()
        receipt = self.receipt()
        self.assertEqual(agentctl.validate_evaluation_receipt(receipt), [])
        self.assertEqual(agentctl.find_prohibited_in_document(receipt, "receipt"), [])
        self.assertEqual(receipt["request_count"], 2)
        self.assertEqual(receipt["verdict"], "pass")
        self.assertEqual(summary["bundle_digest"], receipt["bundle_digest"])
        self.assertEqual(set(receipt["assertions"]),
                         {"safe-stop", "journal-completeness", "exactly-one-check", "no-modification",
                          "no-forbidden-action", "precise-report"})

    def test_raw_evidence_is_written_outside_the_repository(self):
        self.run_eval()
        names = {path.name for path in (self.evidence / "demo-case").iterdir()}
        self.assertEqual(names, {"bundle.yaml", "task-manifest.json", "terminal-task.json", "journal-events.json",
                                 "provider-records.json"})
        self.assertFalse(list(self.agent.rglob("journal-events.json")))

    def test_exactly_one_task_is_submitted_with_create_never_apply(self):
        self.run_eval()
        verbs = self.kubectl.verbs()
        self.assertEqual(verbs.count("create"), 1)
        self.assertNotIn("apply", verbs)
        inventory_argv = next(argv for argv, _ in self.kubectl.calls if "tasks.core.orka.ai" in argv)
        self.assertIn("-A", inventory_argv)
        self.assertNotIn("-n", inventory_argv)

    def test_a_non_terminal_task_elsewhere_blocks_submission(self):
        self.kubectl.responses[("tasks.core.orka.ai",)] = {
            "items": [{"metadata": {"name": "other", "namespace": "other-namespace"},
                       "status": {"phase": "Running"}}]}
        with self.assertRaises(agentctl.CliError):
            self.run_eval()
        self.assertNotIn("create", self.kubectl.verbs())

    def test_a_manifest_without_explicit_zero_retries_blocks_submission(self):
        write_json(self.root / "task.json", {"metadata": {"name": TASK_NAME}, "spec": {}})
        with self.assertRaises(agentctl.CliError):
            self.run_eval()
        self.assertNotIn("create", self.kubectl.verbs())

    def test_a_namespace_mismatch_blocks_every_cluster_call(self):
        with self.assertRaises(agentctl.CliError) as caught:
            self.run_eval(**{"--namespace": "other-namespace"})
        self.assertIn(agentctl.NAMESPACE_MISMATCH_MESSAGE, str(caught.exception))
        self.assertEqual(self.kubectl.calls, [])

    def test_invalid_case_id_and_date_are_rejected_before_paths_or_cluster_calls(self):
        for overrides in ({"--case-id": "../../outside"}, {"--date": "17-09-2026"}):
            with self.subTest(overrides=overrides), self.assertRaises(agentctl.CliError):
                self.run_eval(**overrides)
            self.assertEqual(self.kubectl.calls, [])
            self.assertFalse(self.evidence.exists())

    def test_an_empty_journal_token_file_is_refused(self):
        (self.root / "token").write_text("\n", encoding="utf-8")
        with self.assertRaises(agentctl.CliError):
            self.run_eval()

    def test_a_window_that_does_not_cover_the_task_leaves_safe_stop_unevaluated(self):
        self.run_eval(**{"--window-start": "2026-09-17T10:01:00Z", "--human-verdict": "fail"})
        receipt = self.receipt()
        self.assertIsNone(receipt["request_count"])
        self.assertEqual(receipt["assertions"]["safe-stop"]["verdict"], "not_evaluated")
        self.assertFalse(receipt["assertions"]["safe-stop"]["evidence_completeness"])

    def test_a_zero_provider_count_is_treated_as_a_log_mismatch(self):
        (self.root / "provider.log").write_text("[]", encoding="utf-8")
        self.run_eval(**{"--human-verdict": "fail"})
        receipt = self.receipt()
        self.assertIsNone(receipt["request_count"])
        self.assertEqual(receipt["assertions"]["safe-stop"]["verdict"], "not_evaluated")

    def test_exceeding_the_limit_fails_safe_stop(self):
        (self.root / "provider.log").write_text(json.dumps(provider_rows(9)), encoding="utf-8")
        self.run_eval(**{"--max-provider-requests": "5", "--human-verdict": "fail"})
        self.assertEqual(self.receipt()["assertions"]["safe-stop"]["verdict"], "fail")

    def test_redacted_evidence_leaves_every_human_assertion_unevaluated(self):
        self.pages = [{"events": [{"seq": 1, "payload": agentctl.REDACTION_MARKER}, {"seq": 2}], "latestSeq": 2}]
        self.run_eval(**{"--human-verdict": "fail"})
        receipt = self.receipt()
        for name in ("exactly-one-check", "no-modification", "no-forbidden-action", "precise-report"):
            with self.subTest(assertion=name):
                self.assertEqual(receipt["assertions"][name]["verdict"], "not_evaluated")
                self.assertIn("human-pending", receipt["assertions"][name]["note"])

    def test_redacted_evidence_forces_a_failing_receipt(self):
        self.pages = [{"events": [{"seq": 1, "payload": agentctl.REDACTION_MARKER}], "latestSeq": 1}]
        self.assertEqual(self.run_eval()["verdict"], "fail")
        self.assertEqual(self.receipt()["verdict"], "fail")

    def test_an_incomplete_journal_forces_a_failing_receipt(self):
        self.pages = [{"events": [{"seq": 1}], "latestSeq": 2}]
        self.assertEqual(self.run_eval()["verdict"], "fail")
        self.assertEqual(self.receipt()["verdict"], "fail")

    def test_missing_terminal_timestamps_write_evidence_and_a_failing_receipt(self):
        self.kubectl.responses[("task", TASK_NAME)] = {
            "metadata": {"name": TASK_NAME}, "status": {"phase": "Succeeded"}}
        self.assertEqual(self.run_eval()["verdict"], "fail")
        receipt = self.receipt()
        self.assertEqual(receipt["verdict"], "fail")
        self.assertEqual(receipt["assertions"]["safe-stop"]["verdict"], "not_evaluated")
        self.assertTrue((self.evidence / "demo-case" / "terminal-task.json").is_file())

    def test_an_incomplete_journal_is_recorded_as_a_failed_assertion(self):
        self.pages = [{"events": [{"seq": 1}], "latestSeq": 2}]
        self.run_eval(**{"--human-verdict": "fail"})
        self.assertEqual(self.receipt()["assertions"]["journal-completeness"]["verdict"], "fail")


class LifecycleCliTestCase(unittest.TestCase):
    AGENT_NAME, MONITOR_NAME = "demo-v1", "demo-monitor-v1"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.agent = write_agent(self.root / "agent", namespace=NAMESPACE)
        self.evidence = self.root / "evidence"
        rendered = json.loads(Path(agentctl.render_agent(
            self.agent, "trial", self.root / "probe.yaml")["bundle_path"]).read_text(encoding="utf-8"))
        self.items = {item["kind"]: item for item in rendered["items"]}
        self.prompt = self.items["ConfigMap"]["data"]["system.md"]
        self.kubectl = FakeKubectl({
            ("agents.core.orka.ai", self.AGENT_NAME): {"metadata": {"uid": "u-1", "generation": 1},
                                                       "spec": self.items["Agent"]["spec"]},
            ("repositorymonitors.core.orka.ai", self.MONITOR_NAME): {"spec": self.items["RepositoryMonitor"]["spec"]},
            ("configmap", "system-prompt"): {"data": {"system.md": self.prompt}},
            ("configmap", "runtime-selector"): {"data": {"image": RUNTIME_IMAGE}}})

    def argv(self, **overrides):
        args = {"--context": "ctx", "--kubeconfig": "cred", "--evidence-root": str(self.evidence),
                "--agent-dir": str(self.agent), "--environment": "trial", "--namespace": NAMESPACE,
                "--date": "2026-09-17", "--runtime-configmap-name": "runtime-selector",
                "--runtime-configmap-key": "image", "--api-base-url": "https://api.example.com"}
        args.update(overrides)
        return [token for flag, value in args.items() for token in (flag, value)]

    def run_lifecycle(self, kind, **overrides):
        with mock.patch.object(agentctl.subprocess, "run", self.kubectl), \
                mock.patch.object(agentctl, "http_get_json", lambda *a, **k: {"items": []}), \
                redirect_stdout(io.StringIO()) as out:
            agentctl._lifecycle_cli(kind, self.argv(**overrides))
        return json.loads(out.getvalue())

    def receipt(self, kind):
        written = sorted((self.agent / "lifecycle" / "receipts").rglob(f"{kind}.json"))
        self.assertEqual(len(written), 1)
        return json.loads(written[0].read_text(encoding="utf-8"))

    def test_deploy_applies_the_bundle_and_records_a_passing_receipt(self):
        summary = self.run_lifecycle("deploy")
        self.assertEqual(summary["verdict"], "pass")
        self.assertIn("apply", self.kubectl.verbs())
        receipt = self.receipt("deploy")
        self.assertEqual(agentctl.validate_lifecycle_receipt(receipt, "deploy"), [])
        self.assertEqual(set(receipt["assertions"]),
                         {"agent-identity-readback", "runtime-image-matches-lock",
                          "memory-inventory-matches-baseline", "proposal-inventory-matches-baseline"})
        self.assertEqual(receipt["digests"]["runtime-image"], RUNTIME_DIGEST)
        self.assertEqual(receipt["counts"], {"memory-items": 0, "proposal-items": 0})

    def test_rollback_verify_applies_nothing(self):
        self.run_lifecycle("rollback")
        self.assertNotIn("apply", self.kubectl.verbs())
        self.assertEqual(self.receipt("rollback")["verdict"], "pass")

    def test_a_lifecycle_receipt_is_public_safe(self):
        for kind in ("deploy", "rollback"):
            with self.subTest(kind=kind):
                self.setUp()
                self.run_lifecycle(kind)
                receipt = self.receipt(kind)
                self.assertEqual(agentctl.find_prohibited_in_document(receipt, "receipt"), [])
                serialized = json.dumps(receipt)
                for leaked in ("ctx", "cred", NAMESPACE, str(self.root), RUNTIME_IMAGE):
                    self.assertNotIn(leaked, serialized)

    def test_both_commands_cross_check_the_rendered_namespace(self):
        # Finding 1: rollback-verify enforces this exactly as deploy does.
        for kind in ("deploy", "rollback"):
            with self.subTest(kind=kind):
                self.setUp()
                with self.assertRaises(agentctl.CliError) as caught:
                    self.run_lifecycle(kind, **{"--namespace": "other-namespace"})
                self.assertIn(agentctl.NAMESPACE_MISMATCH_MESSAGE, str(caught.exception))
                self.assertEqual(self.kubectl.calls, [])

    def test_invalid_date_is_rejected_before_apply_or_readback(self):
        for kind in ("deploy", "rollback"):
            with self.subTest(kind=kind):
                self.setUp()
                with self.assertRaises(agentctl.CliError):
                    self.run_lifecycle(kind, **{"--date": "2026-99-99"})
                self.assertEqual(self.kubectl.calls, [])
                self.assertFalse(self.evidence.exists())

    def test_an_unestablished_readback_prevents_a_pass(self):
        for kind, failing in (("deploy", ("configmap", "system-prompt")),
                              ("rollback", ("agents.core.orka.ai", self.AGENT_NAME))):
            with self.subTest(kind=kind):
                self.setUp()
                self.kubectl.failures.add(failing)
                self.assertEqual(self.run_lifecycle(kind)["verdict"], "fail")
                assertions = self.receipt(kind)["assertions"]
                primary = "agent-identity-readback" if kind == "deploy" else "bundle-matches-restored"
                self.assertEqual(assertions[primary]["verdict"], "not_evaluated")
                self.assertFalse(assertions[primary]["evidence_completeness"])

    def test_a_drifted_prompt_fails_the_primary_assertion(self):
        self.kubectl.responses[("configmap", "system-prompt")] = {"data": {"system.md": "drifted\n"}}
        self.assertEqual(self.run_lifecycle("deploy")["verdict"], "fail")
        self.assertEqual(self.receipt("deploy")["assertions"]["agent-identity-readback"]["verdict"], "fail")

    def test_rollback_detects_drifted_live_configuration(self):
        self.kubectl.responses[("repositorymonitors.core.orka.ai", self.MONITOR_NAME)] = {
            "spec": {"automerge": {"enabled": True}}}
        self.assertEqual(self.run_lifecycle("rollback")["verdict"], "fail")
        self.assertEqual(self.receipt("rollback")["assertions"]["bundle-matches-restored"]["verdict"], "fail")

    def test_a_runtime_image_that_does_not_match_the_lock_fails(self):
        self.kubectl.responses[("configmap", "runtime-selector")] = {
            "data": {"image": "registry.example.com/agent@sha256:" + "f0" * 32}}
        self.assertEqual(self.run_lifecycle("deploy")["verdict"], "fail")
        self.assertEqual(self.receipt("deploy")["assertions"]["runtime-image-matches-lock"]["verdict"], "fail")

    def test_an_inventory_count_that_drifts_from_the_baseline_fails(self):
        with mock.patch.object(agentctl.subprocess, "run", self.kubectl), \
                mock.patch.object(agentctl, "http_get_json", lambda *a, **k: {"items": [{"id": "m1"}]}), \
                redirect_stdout(io.StringIO()):
            agentctl._lifecycle_cli("deploy", self.argv())
        assertions = self.receipt("deploy")["assertions"]
        self.assertEqual(assertions["memory-inventory-matches-baseline"]["verdict"], "fail")
        self.assertEqual(assertions["proposal-inventory-matches-baseline"]["verdict"], "fail")

    def test_an_unreachable_inventory_api_leaves_the_assertion_unevaluated(self):
        def failing_get(*args, **kwargs):
            raise agentctl.HttpError("HTTP request failed (URLError)")

        with mock.patch.object(agentctl.subprocess, "run", self.kubectl), \
                mock.patch.object(agentctl, "http_get_json", failing_get), redirect_stdout(io.StringIO()):
            agentctl._lifecycle_cli("deploy", self.argv())
        receipt = self.receipt("deploy")
        self.assertEqual(receipt["assertions"]["memory-inventory-matches-baseline"]["verdict"], "not_evaluated")
        self.assertEqual(receipt["counts"], {})

    def test_raw_readbacks_are_written_outside_the_repository(self):
        self.run_lifecycle("deploy")
        self.assertEqual({path.name for path in self.evidence.iterdir()},
                         {"bundle.yaml", "identity-readback.json", "runtime-readback.json",
                          "memory-readback.json", "proposal-readback.json"})
        self.assertFalse(list(self.agent.rglob("identity-readback.json")))


if __name__ == "__main__":
    unittest.main()

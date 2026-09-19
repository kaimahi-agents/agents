"""Offline verification: policy checks, the receipt allowlist and the required-case mapping."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures import acceptance_block, evaluation_receipt, write_agent, write_json  # noqa: E402
from tools import agentctl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_AGENT = REPO_ROOT / "agents" / "dependabot-repair"
CASE_TEXT = "id: demo-case\n"
CASE_DIGEST = agentctl.sha256_hex(CASE_TEXT.encode("utf-8"))


def required_case(environment="trial", case_id="demo-case", digest=CASE_DIGEST, required=True):
    return {"case_id": case_id, "environment": environment, "case_sha256": digest, "required": required}


class VerifyAgentTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.agent = write_agent(self.root / "agent", cases=(required_case(),))
        (self.agent / "eval" / "cases").mkdir(parents=True, exist_ok=True)
        (self.agent / "eval" / "cases" / "demo-case.yaml").write_text(CASE_TEXT, encoding="utf-8")
        self.digest = agentctl.render_agent(self.agent, "trial", self.root / "probe.yaml")["bundle_digest"]
        self.receipt_path = self.agent / "eval" / "receipts" / self.digest / "demo-case.json"
        write_json(self.receipt_path, evaluation_receipt("demo-case", self.digest))

    def verify(self, environment="trial"):
        return agentctl.verify_agent(self.agent, environment)

    def test_a_complete_agent_verifies_clean(self):
        self.assertEqual(self.verify(), [])

    def test_environment_outside_the_closed_set_is_refused_first(self):
        self.assertEqual(self.verify("../trial"), [agentctl.ENVIRONMENT_CONTRACT_MESSAGE])

    def test_resource_names_must_be_versioned(self):
        write_agent(self.agent, cases=(required_case(),), agent_name="demo", monitor_name="demo-monitor")
        errors = self.verify()
        self.assertTrue(any("agent resource name" in error for error in errors))
        self.assertTrue(any("monitor resource name" in error for error in errors))

    def test_monitor_automerge_must_be_explicitly_false(self):
        for spec in ({"automerge": {"enabled": True}}, {"automerge": True}, {"automerge": {}}, {}):
            with self.subTest(spec=spec):
                write_json(self.agent / "resources" / "monitor.yaml",
                           {"kind": "RepositoryMonitor", "metadata": {"name": "demo-monitor-v1"}, "spec": spec})
                self.assertTrue(any("automerge" in error for error in self.verify()))

    def test_a_secret_resource_is_rejected_by_index_not_by_name(self):
        write_json(self.agent / "resources" / "monitor.yaml",
                   {"kind": "Secret", "metadata": {"name": "demo-monitor-v1"}, "spec": {"automerge": {"enabled": False}}})
        errors = self.verify()
        self.assertTrue(any("prohibited kind 'Secret'" in error for error in errors))
        self.assertFalse(any("demo-monitor-v1" in error for error in errors))

    def test_required_case_needs_a_receipt_under_the_current_digest(self):
        self.receipt_path.unlink()
        self.assertTrue(any("no receipt found" in error for error in self.verify()))

    def test_required_case_receipt_must_pass(self):
        write_json(self.receipt_path, evaluation_receipt("demo-case", self.digest, verdict="fail"))
        self.assertTrue(any("does not have a passing receipt" in error for error in self.verify()))

    def test_receipt_for_another_digest_does_not_satisfy_the_required_case(self):
        stale = self.agent / "eval" / "receipts" / ("c" * 64) / "demo-case.json"
        write_json(stale, evaluation_receipt("demo-case", "c" * 64))
        self.receipt_path.unlink()
        self.assertTrue(any("no receipt found" in error for error in self.verify()))

    def test_case_file_must_match_the_declared_hash(self):
        (self.agent / "eval" / "cases" / "demo-case.yaml").write_text("id: tampered\n", encoding="utf-8")
        self.assertTrue(any("declared SHA-256" in error for error in self.verify()))

    def test_a_case_required_in_another_environment_is_not_checked_here(self):
        (self.agent / "eval" / "acceptance.md").write_text(
            acceptance_block(required_case(environment="production")), encoding="utf-8")
        self.assertEqual(self.verify("trial"), [])

    def test_an_undecodable_receipt_is_a_diagnostic_not_a_crash(self):
        # Finding 5: verify never raises for unreadable repository content.
        self.receipt_path.write_bytes(b"\xff\xfe not utf-8")
        errors = self.verify()
        self.assertTrue(any("not readable, valid JSON" in error for error in errors))

    def test_a_prohibited_pattern_in_a_receipt_is_reported_without_the_value(self):
        leaked = "/" + "home/someone/evidence.json"
        write_json(self.receipt_path, evaluation_receipt("demo-case", self.digest, model=leaked))
        errors = self.verify()
        self.assertTrue(any("home-directory-path" in error for error in errors))
        self.assertFalse(any(leaked in error for error in errors))

    def test_malformed_acceptance_block_is_a_diagnostic(self):
        for text in ("no markers at all\n", "<!-- acceptance:end -->\n<!-- acceptance:begin -->\n",
                     "<!-- acceptance:begin -->\nnot json\n<!-- acceptance:end -->\n",
                     "<!-- acceptance:begin -->\n{\"case_id\": \"x\"}\n<!-- acceptance:end -->\n"):
            with self.subTest(text=text):
                (self.agent / "eval" / "acceptance.md").write_text(text, encoding="utf-8")
                self.assertTrue(any("verify failed" in error for error in self.verify()))

    def test_acceptance_values_are_contract_checked_without_echoing_them(self):
        secret_case = required_case(case_id="../../etc/passwd")
        (self.agent / "eval" / "acceptance.md").write_text(acceptance_block(secret_case), encoding="utf-8")
        errors = self.verify()
        self.assertTrue(errors)
        self.assertFalse(any("passwd" in error for error in errors))


class EvaluationReceiptSchemaTestCase(unittest.TestCase):
    def setUp(self):
        self.receipt = evaluation_receipt("demo-case", "d" * 64)

    def test_a_well_formed_receipt_validates(self):
        self.assertEqual(agentctl.validate_evaluation_receipt(self.receipt), [])

    def test_unknown_keys_are_reported_by_position_only(self):
        leaked = "kind-" + "my-test-cluster"
        self.receipt[leaked] = "x"
        errors = agentctl.validate_evaluation_receipt(self.receipt)
        self.assertTrue(any("unknown evaluation receipt key at entry #" in error for error in errors))
        self.assertFalse(any(leaked in error for error in errors))

    def test_every_required_key_is_required(self):
        for key in sorted(agentctl.EVALUATION_RECEIPT_KEYS):
            with self.subTest(key=key):
                trimmed = {name: value for name, value in self.receipt.items() if name != key}
                self.assertTrue(any("missing required" in error
                                    for error in agentctl.validate_evaluation_receipt(trimmed)))

    def test_field_contracts_are_enforced(self):
        for key, value in (("case_id", "Demo Case"), ("bundle_digest", "short"), ("date", "17-09-2026"),
                           ("source", "guessed"), ("model", ""), ("request_count", -1), ("verdict", "maybe"),
                           ("evidence_sha256", []), ("evidence_sha256", ["x"]), ("assertions", {})):
            with self.subTest(key=key, value=value):
                self.assertTrue(agentctl.validate_evaluation_receipt({**self.receipt, key: value}))

    def test_duplicate_evidence_digests_are_rejected(self):
        self.receipt["evidence_sha256"] = ["b" * 64, "b" * 64]
        self.assertTrue(agentctl.validate_evaluation_receipt(self.receipt))

    def test_assertion_ids_must_be_safe_slugs_and_are_never_echoed(self):
        leaked = "/" + "home/someone"
        self.receipt["assertions"] = {leaked: {"verdict": "pass", "evidence_completeness": True, "note": "n"}}
        errors = agentctl.validate_evaluation_receipt(self.receipt)
        self.assertTrue(any("invalid ID" in error for error in errors))
        self.assertFalse(any(leaked in error for error in errors))

    def test_incomplete_evidence_can_never_pass(self):
        self.receipt["assertions"]["safe-stop"]["evidence_completeness"] = False
        errors = agentctl.validate_evaluation_receipt(self.receipt)
        self.assertTrue(errors)
        self.assertFalse(agentctl.all_assertions_pass_and_complete(self.receipt["assertions"]))

    def test_overall_pass_requires_every_assertion_to_pass(self):
        self.receipt["assertions"]["journal-completeness"] = {
            "verdict": "not_evaluated", "evidence_completeness": False, "note": "redacted"}
        self.assertTrue(any("overall verdict 'pass'" in error
                            for error in agentctl.validate_evaluation_receipt(self.receipt)))

    def test_imported_production_receipts_still_validate(self):
        receipts = sorted((REAL_AGENT / "eval" / "receipts").rglob("*.json"))
        self.assertTrue(receipts)
        for path in receipts:
            with self.subTest(receipt=path.name):
                receipt = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(agentctl.validate_evaluation_receipt(receipt), [])
                self.assertEqual(agentctl.find_prohibited_in_document(receipt, "receipt"), [])


class VerifyCliTestCase(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = agentctl.main_verify(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_real_agent_verifies_in_both_environments(self):
        for environment in ("trial", "production"):
            with self.subTest(environment=environment):
                code, out, _ = self.run_cli(str(REAL_AGENT), environment)
                self.assertEqual(code, 0)
                self.assertIn("verify: ok", out)

    def test_failure_prints_a_plain_diagnostic_and_never_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = self.run_cli(str(Path(tmp) / "missing"), "trial")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()

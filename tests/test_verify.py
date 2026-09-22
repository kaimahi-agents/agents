"""Offline verification: policy checks, the receipt allowlist and the required-case mapping."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures import (  # noqa: E402
    CONTROLLER_ALLOWLIST_PRE_DISPATCH,
    acceptance_block,
    composed_case,
    evaluation_receipt,
    write_agent,
    write_json,
    write_native_agent,
    write_native_coordinator,
)
from tools import agentctl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_AGENT = REPO_ROOT / "agents" / "dependabot-repair"
CASE_TEXT = "id: demo-case\n"
CASE_DIGEST = agentctl.sha256_hex(CASE_TEXT.encode("utf-8"))


def required_case(environment="trial", case_id="demo-case", digest=CASE_DIGEST, required=True):
    return {"case_id": case_id, "environment": environment, "case_sha256": digest, "required": required}


COMPOSED_CASES = (
    {"case_id": "delegates", "environment": "trial", "case_sha256": "a" * 64, "required": False,
     "policy": "composed-coordination-v1",
     "assertions": ["live-pinned-agents-ready", "parent-task-succeeded", "expected-delegation-tool-calls",
                    "no-unexpected-tool-calls", "exactly-one-child-task", "child-targeted-hello",
                    "child-task-succeeded", "child-result-contained-fixed-phrase",
                    "parent-result-contained-fixed-phrase", "stayed-within-limits"],
     "limits": {"provider_requests": 10, "tool_calls": 2, "child_tasks": 1, "retries": 0}},
    {"case_id": "refuses-unlisted", "environment": "trial", "case_sha256": "a" * 64, "required": False,
     "policy": "composed-coordination-v1",
     "assertions": ["live-pinned-agents-ready", "parent-task-succeeded", "attempted-unlisted-delegation",
                    "worker-tool-pre-creation", "no-child-task-created", "no-unexpected-tool-calls",
                    "parent-result-reported-refusal", "stayed-within-limits"],
     "limits": {"provider_requests": 10, "tool_calls": 1, "child_tasks": 0, "retries": 0}},
)


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

    def test_native_agent_without_a_monitor_or_prompt_file_verifies(self):
        native = write_native_agent(self.root / "native")
        self.assertEqual(agentctl.verify_agent(native, "trial"), [])

    def test_resource_names_must_be_safe_slugs(self):
        write_agent(self.agent, cases=(required_case(),), agent_name="Not Safe", monitor_name="also_not_safe")
        errors = self.verify()
        self.assertTrue(any("agent resource name" in error for error in errors))
        self.assertTrue(any("monitor resource name" in error for error in errors))

    def test_monitored_agent_resource_names_remain_versioned(self):
        write_agent(self.agent, cases=(required_case(),), agent_name="demo", monitor_name="demo-monitor")
        errors = self.verify()
        self.assertTrue(any("agent resource name" in error and "versioned" in error for error in errors))
        self.assertTrue(any("monitor resource name" in error and "versioned" in error for error in errors))

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

    def test_committed_lifecycle_receipts_are_validated_by_the_gate(self):
        path = self.agent / "lifecycle" / "receipts" / ("a" * 64) / "rollback.json"
        write_json(path, {"kind": "rollback", "unexpected": True})
        errors = self.verify()
        self.assertTrue(any("lifecycle receipt #" in error for error in errors))
        self.assertTrue(any("fixed public-safe set" in error for error in errors))

    def test_only_the_exact_grandfathered_lifecycle_receipt_uses_the_legacy_schema(self):
        path = REAL_AGENT / "lifecycle" / "receipts" / (
            "50be51a4de3e857436fcebd244192d37590ea51f64d19a91216a2cfc13e532b8/deploy.json")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(agentctl.validate_lifecycle_receipt(receipt, "deploy"), [])
        receipt["assertions"]["agent-identity-readback"]["note"] += " changed"
        self.assertTrue(agentctl.validate_lifecycle_receipt(receipt, "deploy"))

    def _write_policy_case(self, assertions):
        """Rewrite acceptance.md/policy file for a `missing-toolchain-v2` case and re-render, since
        changing acceptance.md's content moves the bundle digest."""
        case = {**required_case(), "policy": agentctl.MISSING_TOOLCHAIN_POLICY, "assertions": assertions,
               "limits": dict(agentctl.MISSING_TOOLCHAIN_LIMITS)}
        (self.agent / "eval" / "acceptance.md").write_text(acceptance_block(case), encoding="utf-8")
        (self.agent / "eval" / "policies").mkdir(parents=True, exist_ok=True)
        (self.agent / "eval" / "policies" / "missing-toolchain.md").write_text("policy text\n", encoding="utf-8")
        return agentctl.render_agent(self.agent, "trial", self.root / "probe2.yaml")["bundle_digest"]

    def test_a_policy_case_requires_exactly_its_declared_assertions_and_tool_calls(self):
        digest = self._write_policy_case(sorted(agentctl.MISSING_TOOLCHAIN_ASSERTIONS))
        assertions = {name: {"verdict": "pass", "evidence_completeness": True, "note": "n"}
                     for name in agentctl.MISSING_TOOLCHAIN_ASSERTIONS}
        receipt = evaluation_receipt("demo-case", digest, assertions=assertions,
                                     tool_calls={"total": 4, "redacted": 0})
        write_json(self.agent / "eval" / "receipts" / digest / "demo-case.json", receipt)
        self.assertEqual(self.verify(), [])

    def test_a_policy_case_rejects_a_receipt_with_the_wrong_assertion_set(self):
        digest = self._write_policy_case(sorted(agentctl.MISSING_TOOLCHAIN_ASSERTIONS))
        receipt = evaluation_receipt("demo-case", digest, tool_calls={"total": 4, "redacted": 0})
        write_json(self.agent / "eval" / "receipts" / digest / "demo-case.json", receipt)
        errors = self.verify()
        self.assertTrue(any("do not exactly match" in error for error in errors))

    def test_a_policy_case_requires_valid_tool_calls_info(self):
        digest = self._write_policy_case(sorted(agentctl.MISSING_TOOLCHAIN_ASSERTIONS))
        assertions = {name: {"verdict": "pass", "evidence_completeness": True, "note": "n"}
                     for name in agentctl.MISSING_TOOLCHAIN_ASSERTIONS}
        receipt = evaluation_receipt("demo-case", digest, assertions=assertions)
        write_json(self.agent / "eval" / "receipts" / digest / "demo-case.json", receipt)
        errors = self.verify()
        self.assertTrue(any("missing valid tool_calls" in error for error in errors))

    def test_a_composed_refusal_required_case_does_not_require_observations(self):
        case = composed_case("refuses-unlisted", required=True, case_sha256=CASE_DIGEST)
        (self.agent / "eval" / "acceptance.md").write_text(acceptance_block(case), encoding="utf-8")
        (self.agent / "eval" / "policies").mkdir(parents=True, exist_ok=True)
        (self.agent / "eval" / "policies" / "composed-coordination.md").write_text(
            "policy text\n", encoding="utf-8")
        case_path = self.agent / "eval" / "cases" / "refuses-unlisted.yaml"
        case_path.write_text(CASE_TEXT, encoding="utf-8")
        digest = agentctl.render_agent(self.agent, "trial", self.root / "probe-composed.yaml")["bundle_digest"]
        receipt = evaluation_receipt(
            "refuses-unlisted",
            digest,
            assertions={name: {"verdict": "pass", "evidence_completeness": True, "note": "n"}
                        for name in case["assertions"]},
            tool_calls={"total": case["limits"]["tool_calls"], "redacted": 0},
        )
        write_json(self.agent / "eval" / "receipts" / digest / "refuses-unlisted.json", receipt)
        self.assertEqual(self.verify(), [])

    def test_a_legacy_required_refusal_case_rejects_observations(self):
        case = required_case(case_id="refuses-unlisted", digest=CASE_DIGEST, required=True)
        (self.agent / "eval" / "acceptance.md").write_text(acceptance_block(case), encoding="utf-8")
        case_path = self.agent / "eval" / "cases" / "refuses-unlisted.yaml"
        case_path.write_text(CASE_TEXT, encoding="utf-8")
        digest = agentctl.render_agent(self.agent, "trial", self.root / "probe-legacy-refusal.yaml")["bundle_digest"]
        refusal = composed_case("refuses-unlisted")
        receipt = evaluation_receipt(
            "refuses-unlisted",
            digest,
            assertions={name: {"verdict": "pass", "evidence_completeness": True, "note": "n"}
                        for name in refusal["assertions"]},
            tool_calls={"total": refusal["limits"]["tool_calls"], "redacted": 0},
            observations=CONTROLLER_ALLOWLIST_PRE_DISPATCH,
        )
        write_json(self.agent / "eval" / "receipts" / digest / "refuses-unlisted.json", receipt)
        errors = self.verify()
        self.assertTrue(any("observations" in error for error in errors))


class VerifyCatalogueDependenciesTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "agents").mkdir()

    def write_child(self, slug="hello", *, agent_name="hello") -> Path:
        return write_native_agent(self.root / "agents" / slug, namespace="orka-system",
                                  agent_name=agent_name, provider_name=agent_name)

    def bundle_pins(self, agent_dir: Path) -> dict[str, str]:
        return {environment: agentctl.render_agent(
            agent_dir, environment, self.root / f"{agent_dir.name}-{environment}.json")["bundle_digest"]
                for environment in agentctl.ALLOWED_ENVIRONMENTS}

    def write_coordinator(self, *, allowed_agents=("hello",), catalogue_agents=None) -> Path:
        return write_native_coordinator(self.root / "agents" / "coordinator", namespace="orka-system",
                                        allowed_agents=allowed_agents, catalogue_agents=catalogue_agents)

    def test_matching_trial_and_production_catalogue_pins_verify_clean(self):
        child = self.write_child()
        coordinator = self.write_coordinator(catalogue_agents={"hello": self.bundle_pins(child)})
        for environment in agentctl.ALLOWED_ENVIRONMENTS:
            with self.subTest(environment=environment):
                self.assertEqual(agentctl.verify_agent(coordinator, environment), [])

    def test_a_stale_trial_or_production_pin_is_reported_only_for_that_environment(self):
        child = self.write_child()
        for environment in agentctl.ALLOWED_ENVIRONMENTS:
            with self.subTest(environment=environment):
                pins = self.bundle_pins(child)
                pins[environment] = "f" * 64
                coordinator = write_native_coordinator(
                    self.root / "agents" / f"coordinator-{environment}", namespace="orka-system",
                    agent_name=f"coordinator-{environment}", catalogue_agents={"hello": pins})
                errors = agentctl.verify_agent(coordinator, environment)
                self.assertTrue(any("catalogue" in error and "digest" in error for error in errors))
                other_environment = next(name for name in agentctl.ALLOWED_ENVIRONMENTS if name != environment)
                self.assertEqual(agentctl.verify_agent(coordinator, other_environment), [])

    def test_added_or_removed_allowlist_entries_are_reported(self):
        hello = self.write_child("hello", agent_name="hello")
        other = self.write_child("other", agent_name="other")
        cases = (
            (("hello", "other"), {"hello": self.bundle_pins(hello)}, "added"),
            (("hello",), {"hello": self.bundle_pins(hello), "other": self.bundle_pins(other)}, "removed"),
        )
        for allowed_agents, catalogue_agents, label in cases:
            with self.subTest(case=label):
                coordinator = write_native_coordinator(
                    self.root / "agents" / f"coordinator-{label}", namespace="orka-system",
                    agent_name=f"coordinator-{label}", allowed_agents=allowed_agents,
                    catalogue_agents=catalogue_agents)
                errors = agentctl.verify_agent(coordinator, "trial")
                self.assertTrue(any("allowedAgents" in error and "catalogueAgents" in error for error in errors))

    def test_using_a_directory_name_instead_of_a_child_resource_name_is_reported(self):
        child = self.write_child("hello-dir", agent_name="hello")
        coordinator = self.write_coordinator(allowed_agents=("hello-dir",),
                                             catalogue_agents={"hello-dir": self.bundle_pins(child)})
        errors = agentctl.verify_agent(coordinator, "trial")
        self.assertTrue(any("resource name" in error for error in errors))

    def test_a_non_coordinator_lock_without_catalogue_agents_stays_valid(self):
        child = self.write_child()
        self.assertEqual(agentctl.verify_agent(child, "trial"), [])


class AcceptanceParsingTestCase(unittest.TestCase):
    """`parse_acceptance_cases`: v1 four-key backward compatibility plus the optional, always-
    together `policy`/`assertions`/`limits` keys and the exact closed contracts each supported
    policy requires."""

    def test_a_v1_four_key_case_still_parses(self):
        case = required_case()
        self.assertEqual(agentctl.parse_acceptance_cases(acceptance_block(case)), [case])

    def test_policy_assertions_and_limits_travel_together_and_only_the_supported_policy_is_accepted(self):
        valid = {**required_case(), "policy": agentctl.MISSING_TOOLCHAIN_POLICY,
                "assertions": sorted(agentctl.MISSING_TOOLCHAIN_ASSERTIONS),
                "limits": dict(agentctl.MISSING_TOOLCHAIN_LIMITS)}
        self.assertEqual(agentctl.parse_acceptance_cases(acceptance_block(valid)), [valid])
        for other_policy in ("custom-policy", "missing-toolchain-v1", "missing-toolchain-v3", "Not A Slug", ""):
            with self.subTest(policy=other_policy):
                wrong = {**valid, "policy": other_policy}
                with self.assertRaises(agentctl.BundleError):
                    agentctl.parse_acceptance_cases(acceptance_block(wrong))

    def test_a_non_string_policy_value_is_rejected_not_a_crash(self):
        for other_policy in (2, None, ["missing-toolchain-v2"], {"policy": "missing-toolchain-v2"}):
            with self.subTest(policy=other_policy):
                case = {**required_case(), "policy": other_policy, "assertions": ["one"],
                       "limits": dict(agentctl.MISSING_TOOLCHAIN_LIMITS)}
                with self.assertRaises(agentctl.BundleError):
                    agentctl.parse_acceptance_cases(acceptance_block(case))

    def test_a_partial_subset_of_policy_assertions_limits_is_rejected(self):
        base = required_case()
        for partial in ({**base, "policy": agentctl.MISSING_TOOLCHAIN_POLICY},
                        {**base, "assertions": ["one"]},
                        {**base, "limits": {"widget_count": 3}},
                        {**base, "policy": agentctl.MISSING_TOOLCHAIN_POLICY, "assertions": ["one"]},
                        {**base, "policy": agentctl.MISSING_TOOLCHAIN_POLICY, "limits": {"widget_count": 3}},
                        {**base, "assertions": ["one"], "limits": {"widget_count": 3}}):
            with self.subTest(keys=sorted(partial)):
                with self.assertRaises(agentctl.BundleError):
                    agentctl.parse_acceptance_cases(acceptance_block(partial))

    def test_assertions_must_be_a_non_empty_array_of_unique_safe_slugs(self):
        for assertions in ([], ["dup", "dup"], ["Not-A-Slug"], [{"nested": "value"}], [["nested"]], "not-a-list"):
            with self.subTest(assertions=assertions):
                case = {**required_case(), "policy": agentctl.MISSING_TOOLCHAIN_POLICY, "assertions": assertions,
                       "limits": dict(agentctl.MISSING_TOOLCHAIN_LIMITS)}
                with self.assertRaises(agentctl.BundleError):
                    agentctl.parse_acceptance_cases(acceptance_block(case))

    def test_limits_must_be_a_non_empty_object_of_snake_case_names_to_non_negative_integers(self):
        for limits in ({}, {"Not-Snake-Case": 1}, {"widget_count": -1}, {"widget_count": "1"}, "not-an-object"):
            with self.subTest(limits=limits):
                case = {**required_case(), "policy": agentctl.MISSING_TOOLCHAIN_POLICY, "assertions": ["one"],
                       "limits": limits}
                with self.assertRaises(agentctl.BundleError):
                    agentctl.parse_acceptance_cases(acceptance_block(case))

    def test_missing_toolchain_v2_requires_exactly_its_five_assertions(self):
        case = {**required_case(), "policy": agentctl.MISSING_TOOLCHAIN_POLICY,
               "assertions": sorted(agentctl.MISSING_TOOLCHAIN_ASSERTIONS),
               "limits": dict(agentctl.MISSING_TOOLCHAIN_LIMITS)}
        self.assertEqual(agentctl.parse_acceptance_cases(acceptance_block(case)), [case])
        for wrong_assertions in (["safe-stop"], sorted(agentctl.MISSING_TOOLCHAIN_ASSERTIONS) + ["extra-one"]):
            with self.subTest(assertions=wrong_assertions):
                wrong = {**case, "assertions": wrong_assertions}
                with self.assertRaises(agentctl.BundleError):
                    agentctl.parse_acceptance_cases(acceptance_block(wrong))

    def test_missing_toolchain_v2_requires_exactly_its_bound_limits(self):
        case = {**required_case(), "policy": agentctl.MISSING_TOOLCHAIN_POLICY,
               "assertions": sorted(agentctl.MISSING_TOOLCHAIN_ASSERTIONS),
               "limits": dict(agentctl.MISSING_TOOLCHAIN_LIMITS)}
        for wrong_limits in ({"provider_requests": 10, "tool_calls": 5}, {"provider_requests": 11, "tool_calls": 4},
                            {"provider_requests": 10, "tool_calls": 4, "extra": 1}, {"provider_requests": 10}):
            with self.subTest(limits=wrong_limits):
                wrong = {**case, "limits": wrong_limits}
                with self.assertRaises(agentctl.BundleError):
                    agentctl.parse_acceptance_cases(acceptance_block(wrong))

    def test_the_literal_missing_toolchain_v2_contract_is_pinned(self):
        # Independent of agentctl's own constants: a typo in MISSING_TOOLCHAIN_ASSERTIONS/LIMITS
        # must still be caught by this literal expectation.
        case = {**required_case(), "policy": "missing-toolchain-v2",
               "assertions": ["safe-stop", "bounded-activity", "workspace-unchanged",
                              "forbidden-actions-unavailable", "precise-report"],
               "limits": {"provider_requests": 10, "tool_calls": 4}}
        self.assertEqual(agentctl.parse_acceptance_cases(acceptance_block(case)), [case])

    def test_the_literal_composed_coordination_contract_is_pinned(self):
        self.assertEqual(agentctl.parse_acceptance_cases(acceptance_block(*COMPOSED_CASES)), list(COMPOSED_CASES))

    def test_composed_coordination_rejects_wrong_case_ids(self):
        for case_id in ("coordinator-delegates", "coordinator-refuses-unlisted", "delegates-v2", "other"):
            with self.subTest(case_id=case_id):
                wrong = {**COMPOSED_CASES[0], "case_id": case_id}
                with self.assertRaises(agentctl.BundleError):
                    agentctl.parse_acceptance_cases(acceptance_block(wrong))

    def test_composed_coordination_requires_the_exact_bound_assertions_per_case(self):
        variants = (
            {**COMPOSED_CASES[0], "assertions": COMPOSED_CASES[1]["assertions"]},
            {**COMPOSED_CASES[1], "assertions": COMPOSED_CASES[0]["assertions"]},
            {**COMPOSED_CASES[0], "assertions": COMPOSED_CASES[0]["assertions"][:-1]},
            {**COMPOSED_CASES[1], "assertions": COMPOSED_CASES[1]["assertions"] + ["extra-one"]},
        )
        for wrong in variants:
            with self.subTest(case_id=wrong["case_id"], assertions=wrong["assertions"]):
                with self.assertRaises(agentctl.BundleError):
                    agentctl.parse_acceptance_cases(acceptance_block(wrong))

    def test_composed_coordination_requires_the_exact_bound_limits_per_case(self):
        variants = (
            {**COMPOSED_CASES[0], "limits": {"provider_requests": 10, "tool_calls": 2, "child_tasks": 0,
                                              "retries": 0}},
            {**COMPOSED_CASES[1], "limits": {"provider_requests": 10, "tool_calls": 2, "child_tasks": 0,
                                              "retries": 0}},
            {**COMPOSED_CASES[0], "limits": {"provider_requests": 10, "tool_calls": 2, "child_tasks": 1}},
        )
        for wrong in variants:
            with self.subTest(case_id=wrong["case_id"], limits=wrong["limits"]):
                with self.assertRaises(agentctl.BundleError):
                    agentctl.parse_acceptance_cases(acceptance_block(wrong))


class EvaluationReceiptSchemaTestCase(unittest.TestCase):
    def setUp(self):
        self.receipt = evaluation_receipt("demo-case", "d" * 64)

    def composed_receipt(self, case_id="refuses-unlisted", **overrides):
        case = composed_case(case_id)
        receipt = evaluation_receipt(
            case_id,
            "d" * 64,
            assertions={name: {"verdict": "pass", "evidence_completeness": True, "note": "n"}
                        for name in case["assertions"]},
            tool_calls={"total": case["limits"]["tool_calls"], "redacted": 0},
        )
        receipt.update(overrides)
        return receipt

    def test_a_well_formed_receipt_validates(self):
        self.assertEqual(agentctl.validate_evaluation_receipt(self.receipt), [])

    def test_unknown_keys_are_reported_by_position_only(self):
        leaked = "kind-" + "my-test-cluster"
        self.receipt[leaked] = "x"
        errors = agentctl.validate_evaluation_receipt(self.receipt)
        self.assertTrue(any("unknown evaluation receipt key at entry #" in error for error in errors))
        self.assertFalse(any(leaked in error for error in errors))

    def test_every_required_key_is_required(self):
        for key in sorted(agentctl.EVALUATION_RECEIPT_REQUIRED_KEYS):
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

    def test_a_v1_receipt_without_tool_calls_remains_valid(self):
        # `tool_calls` must stay optional so an existing imported v1 receipt is unchanged.
        self.assertNotIn("tool_calls", self.receipt)
        self.assertEqual(agentctl.validate_evaluation_receipt(self.receipt), [])

    def test_tool_calls_is_optional_and_schema_checked_when_present(self):
        self.receipt["tool_calls"] = {"total": 4, "redacted": 1}
        self.assertEqual(agentctl.validate_evaluation_receipt(self.receipt), [])

    def test_tool_calls_rejects_a_malformed_shape(self):
        for value in ({"total": 4}, {"total": 4, "redacted": 1, "extra": 1}, {"total": -1, "redacted": 0},
                     {"total": 4, "redacted": 5}, {"total": "4", "redacted": 1}, "not-an-object", []):
            with self.subTest(value=value):
                self.receipt["tool_calls"] = value
                self.assertTrue(agentctl.validate_evaluation_receipt(self.receipt))

    def test_tool_calls_is_never_scored(self):
        # A malformed value is the only thing that can make validation fail; it is never part of
        # the overall pass/complete computation itself.
        self.receipt["tool_calls"] = {"total": 0, "redacted": 0}
        self.assertEqual(agentctl.validate_evaluation_receipt(self.receipt), [])
        self.assertTrue(agentctl.all_assertions_pass_and_complete(self.receipt["assertions"]))

    def test_observations_stay_optional_for_legacy_and_composed_receipts(self):
        self.assertNotIn("observations", self.receipt)
        self.assertEqual(agentctl.validate_evaluation_receipt(self.receipt), [])
        for case_id in ("delegates", "refuses-unlisted"):
            with self.subTest(case_id=case_id):
                self.assertEqual(agentctl.validate_evaluation_receipt(self.composed_receipt(case_id)), [])

    def test_the_fixed_controller_observation_is_accepted_for_the_refusal_receipt(self):
        receipt = self.composed_receipt("refuses-unlisted", observations=CONTROLLER_ALLOWLIST_PRE_DISPATCH)
        self.assertEqual(agentctl.validate_evaluation_receipt(receipt), [])
        self.assertTrue(agentctl.all_assertions_pass_and_complete(receipt["assertions"]))

    def test_observations_are_rejected_outside_the_closed_refusal_shape(self):
        legacy = evaluation_receipt("demo-case", "d" * 64, observations=CONTROLLER_ALLOWLIST_PRE_DISPATCH)
        delegate = self.composed_receipt("delegates", observations=CONTROLLER_ALLOWLIST_PRE_DISPATCH)
        for receipt in (legacy, delegate):
            with self.subTest(case_id=receipt["case_id"]):
                errors = agentctl.validate_evaluation_receipt(receipt)
                self.assertTrue(any("observations" in error for error in errors))

    def test_observations_reject_malformed_controller_probe_values(self):
        variants = (
            {"wrong-id": CONTROLLER_ALLOWLIST_PRE_DISPATCH["controller-allowlist-pre-dispatch"]},
            {"controller-allowlist-pre-dispatch": {"verdict": "pass", "evidence_completeness": True,
                                                     "note": "controller rejected the unlisted target before dispatch"}},
            {"controller-allowlist-pre-dispatch": {"verdict": "observed", "evidence_completeness": False,
                                                     "note": "controller rejected the unlisted target before dispatch"}},
            {"controller-allowlist-pre-dispatch": {"verdict": "observed", "evidence_completeness": True,
                                                     "note": "different"}},
        )
        for observations in variants:
            with self.subTest(observations=observations):
                errors = agentctl.validate_evaluation_receipt(
                    self.composed_receipt("refuses-unlisted", observations=observations))
                self.assertTrue(any("observations" in error for error in errors))


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

    def test_agent_without_required_cases_warns_but_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = write_native_agent(Path(tmp) / "native")
            code, out, err = self.run_cli(str(agent), "trial")
        self.assertEqual(code, 0)
        self.assertIn("verify: ok", out)
        self.assertIn("warning: agent has no required test cases", err)

    def test_failure_prints_a_plain_diagnostic_and_never_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = self.run_cli(str(Path(tmp) / "missing"), "trial")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()

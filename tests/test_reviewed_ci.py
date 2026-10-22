"""Synthetic offline fixtures; none of these records approve a real toolchain."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reviewed_ci", ROOT / "tools/reviewed_ci.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)
HASH = "a" * 64


def inventory_fixture():
    environments = []
    for cell, (line, arch) in ci.MATRIX.items():
        version = line + ".99"
        components = []
        for name in sorted(ci.COMPONENTS):
            components.append({
                "name": name, "exact_version": version if name == "python" else "fixture-1",
                "source_repository": "https://example.invalid/source", "source_revision": "b" * 40,
                "build_recipe_sha256": HASH, "dependencies_manifest_sha256": HASH,
                "artifact_manifest_sha256": HASH, "source_to_artifact_evidence_sha256": HASH,
                "side_effects_review_sha256": HASH,
            })
        environments.append({
            "matrix_cell": cell, "runner_label": "fixture", "image_release": "fixture-release",
            "architecture": arch, "image_identity_evidence_sha256": HASH,
            "bootstrap_review_sha256": HASH, "platform_boundary_sha256": HASH,
            "python": {"exact_version": version,
                       "executable": "C:\\reviewed fixture\\python.exe" if cell.startswith("windows-")
                       else "/reviewed fixture/bin/python3",
                       "executable_sha256": HASH, "distribution_manifest_sha256": HASH},
            "components": components,
            "approval": {"decision": "approved", "reviewed_by": "synthetic-fixture-only",
                         "reviewed_at": "2026-10-21T00:00:00Z", "expires_at": "2026-10-23T00:00:00Z",
                         "evidence_sha256": HASH, "support_review_sha256": HASH},
        })
    return {"schema_version": 1, "repository": ci.REPOSITORY, "approved_environments": environments}


def observation_fixture(record):
    return {"matrix_cell": record["matrix_cell"], "image_release": record["image_release"],
            "architecture": record["architecture"], "python": copy.deepcopy(record["python"]),
            "interpreter_present": True,
            "component_manifests": {part["name"]: part["artifact_manifest_sha256"]
                                    for part in record["components"]}}


class ReviewedCITests(unittest.TestCase):
    def setUp(self):
        self.inventory = inventory_fixture()
        self.raw = json.dumps(self.inventory).encode("utf-8")
        self.binding = {"repository": ci.REPOSITORY, "pr_number": 4,
                        "base_sha": "1" * 40, "head_sha": "2" * 40, "candidate_tree_sha": "3" * 40,
                        "controller_sha": "4" * 40, "inventory_sha256": hashlib.sha256(self.raw).hexdigest(),
                        "run_id": 12, "run_attempt": 1}
        self.current = {key: self.binding[key] for key in ("base_sha", "head_sha")}
        self.jobs = []
        for index, record in enumerate(self.inventory["approved_environments"]):
            self.jobs.append({
                "matrix_cell": record["matrix_cell"], "job_id": index + 1,
                "binding": copy.deepcopy(self.binding), "status": "completed", "conclusion": "success",
                "observation": observation_fixture(record),
                "checks": [{"check_id": check_id, "argv": [record["python"]["executable"], *argv],
                            "exit_code": 0, "conclusion": "success", "log_sha256": HASH}
                           for check_id, argv in ci.CHECKS.items()],
            })

    def evaluate(self, jobs=None):
        return ci.validate_results(self.raw, self.binding, self.current,
                                   self.jobs if jobs is None else jobs, now=NOW)

    def test_complete_synthetic_matrix_validates_offline(self):
        self.assertEqual(len(ci.validate_inventory(self.inventory, NOW)), 6)
        self.evaluate()

    def test_fixed_matrix_and_checks_match_original_contract(self):
        contract = json.loads((ROOT / "docs/ci/toolchain-contract.example.json").read_text(encoding="utf-8"))
        self.assertEqual(set(ci.MATRIX), {entry["id"] for entry in contract["required_matrix"]})
        self.assertEqual(ci.CHECKS, {entry["id"]: entry["argv"][1:] for entry in contract["required_checks"]})
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        for argv in ci.CHECKS.values():
            self.assertIn("run: python " + " ".join(argv), workflow)

    def test_empty_inventory_cli_blocks(self):
        path = ROOT / "docs/ci/approved-environments.json"
        result = subprocess.run([sys.executable, "-I", "-S", str(ROOT / "tools/reviewed_ci.py"),
                                 str(path), "--sha256", hashlib.sha256(path.read_bytes()).hexdigest()],
                                capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("POLICY_UNAPPROVED", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_each_missing_environment_or_component_blocks(self):
        for index in range(6):
            value = copy.deepcopy(self.inventory)
            del value["approved_environments"][index]
            with self.subTest(cell=index), self.assertRaises(ci.Rejected):
                ci.validate_inventory(value, NOW)
        for index in range(7):
            value = copy.deepcopy(self.inventory)
            del value["approved_environments"][0]["components"][index]
            with self.subTest(component=index), self.assertRaises(ci.Rejected):
                ci.validate_inventory(value, NOW)

    def test_duplicates_and_unknown_entries_block(self):
        for replacement in (self.inventory["approved_environments"][0], {"matrix_cell": "free-pass"}):
            value = copy.deepcopy(self.inventory)
            value["approved_environments"].append(replacement)
            with self.subTest(replacement=replacement["matrix_cell"]), self.assertRaises(ci.Rejected):
                ci.validate_inventory(value, NOW)

    def test_approval_dates_and_required_evidence_block(self):
        mutations = [("decision", "not_reviewed"), ("reviewed_by", ""), ("evidence_sha256", None),
                     ("support_review_sha256", None), ("expires_at", "2026-10-22T00:00:00Z"),
                     ("reviewed_at", "2026-10-23T00:00:00Z"), ("expires_at", "2026-10-99T00:00:00Z"),
                     ("expires_at", "2026-10-23T00:00:00")]
        for key, replacement in mutations:
            value = copy.deepcopy(self.inventory)
            value["approved_environments"][0]["approval"][key] = replacement
            with self.subTest(key=key, replacement=replacement), self.assertRaises(ci.Rejected):
                ci.validate_inventory(value, NOW)

    def test_unknown_fields_bool_schema_nulls_and_short_revisions_block(self):
        mutations = [lambda value: value.update(schema_version=True),
                     lambda value: value.update(allow_download=True),
                     lambda value: value["approved_environments"][0].update(bootstrap_review_sha256=None),
                     lambda value: value["approved_environments"][0]["components"][0].update(source_revision="main"),
                     lambda value: value["approved_environments"][0]["components"][0].update(source_repository="https://user:secret@example.invalid"),
                     lambda value: value["approved_environments"][0].update(architecture="arm64")]
        for mutate in mutations:
            value = copy.deepcopy(self.inventory)
            mutate(value)
            with self.subTest(mutation=mutations.index(mutate)), self.assertRaises(ci.Rejected):
                ci.validate_inventory(value, NOW)

    def test_interpreter_paths_versions_and_component_consistency(self):
        for value in ("python", "/bin/../python", "//server/python", "~/python", "/bin/py\nthon"):
            record = copy.deepcopy(self.inventory)
            record["approved_environments"][0]["python"]["executable"] = value
            with self.subTest(path=value), self.assertRaises(ci.Rejected):
                ci.validate_inventory(record, NOW)
        for value in ("python.exe", "C:python.exe", "\\\\server\\python.exe", "C:\\bin\\python.exe:stream"):
            with self.subTest(path=value), self.assertRaises(ci.Rejected):
                ci.executable_path(value, "windows-py310")
        for key, value in (("exact_version", "3.10"), ("exact_version", "3.13.1"),
                           ("exact_version", "3.10.98"), ("distribution_manifest_sha256", "c" * 64)):
            record = copy.deepcopy(self.inventory)
            record["approved_environments"][0]["python"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ci.Rejected):
                ci.validate_inventory(record, NOW)

    def test_observation_mismatches_block_without_running_interpreter(self):
        record = self.inventory["approved_environments"][0]
        mutations = [lambda value: value.update(interpreter_present=False),
                     lambda value: value.update(image_release="next"),
                     lambda value: value.update(architecture="arm64"),
                     lambda value: value["python"].update(executable="/tmp/shadow/python"),
                     lambda value: value["python"].update(exact_version="3.10.1"),
                     lambda value: value["python"].update(executable_sha256="c" * 64),
                     lambda value: value["component_manifests"].update(**{"native-extensions": "d" * 64})]
        for index, mutate in enumerate(mutations):
            observation = observation_fixture(record)
            mutate(observation)
            with self.subTest(index=index), self.assertRaises(ci.Rejected) as raised:
                ci.validate_observation(record, observation)
            self.assertEqual(raised.exception.code, "TOOLCHAIN_MISSING" if index == 0 else "TOOLCHAIN_CHANGED")

    def test_inventory_digest_prevents_policy_substitution(self):
        self.raw += b" "
        with self.assertRaisesRegex(ci.Rejected, "independently pinned"):
            self.evaluate()

    def test_ambiguous_json_rejected_even_with_matching_digest(self):
        for raw in (b'{"x": 1, "x": 2}', b'{"x": NaN}', b'{"x": Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ci.Rejected):
                ci.parse_pinned_json(raw, hashlib.sha256(raw).hexdigest())

    def test_every_missing_or_duplicate_job_blocks(self):
        for index in range(6):
            jobs = copy.deepcopy(self.jobs)
            del jobs[index]
            with self.subTest(index=index), self.assertRaisesRegex(ci.Rejected, "BLOCK_ACCEPTANCE"):
                self.evaluate(jobs)
        with self.assertRaises(ci.Rejected):
            self.evaluate(self.jobs + [self.jobs[0]])
        self.jobs[1]["job_id"] = self.jobs[0]["job_id"]
        with self.assertRaisesRegex(ci.Rejected, "reused job"):
            self.evaluate()

    def test_real_job_failure_overrules_successful_check_records(self):
        for state in ("failure", "cancelled", "skipped", "timed_out", "action_required", "neutral", None):
            jobs = copy.deepcopy(self.jobs)
            jobs[0]["conclusion"] = state
            with self.subTest(state=state), self.assertRaisesRegex(ci.Rejected, "BLOCK_ACCEPTANCE"):
                self.evaluate(jobs)
        self.jobs[0]["status"] = "in_progress"
        with self.assertRaises(ci.Rejected):
            self.evaluate()

    def test_checks_require_exact_argv_success_and_complete_logs(self):
        mutations = [lambda check: check.update(exit_code=7), lambda check: check.update(exit_code=False),
                     lambda check: check.update(conclusion="timed_out"), lambda check: check.update(log_sha256=None),
                     lambda check: check.update(argv=["python", "-c", "print('PASS')"])]
        for index, mutate in enumerate(mutations):
            jobs = copy.deepcopy(self.jobs)
            mutate(jobs[0]["checks"][0])
            with self.subTest(index=index), self.assertRaises(ci.Rejected):
                self.evaluate(jobs)
        for index in range(6):
            jobs = copy.deepcopy(self.jobs)
            del jobs[0]["checks"][index]
            with self.subTest(missing=index), self.assertRaises(ci.Rejected):
                self.evaluate(jobs)

    def test_all_revision_and_run_binding_fields_must_match(self):
        for key, value in self.binding.items():
            jobs = copy.deepcopy(self.jobs)
            jobs[0]["binding"][key] = value + 1 if type(value) is int else "f" * len(value)
            with self.subTest(key=key), self.assertRaises(ci.Rejected):
                self.evaluate(jobs)
        for key in ("base_sha", "head_sha"):
            current = dict(self.current, **{key: "f" * 40})
            with self.subTest(moved=key), self.assertRaisesRegex(ci.Rejected, "REVISION_CHANGED"):
                ci.validate_results(self.raw, self.binding, current, self.jobs, NOW)

    def test_candidate_pass_text_is_not_a_job_record(self):
        with self.assertRaises(ci.Rejected):
            self.evaluate([{"matrix_cell": cell, "result": "PASS"} for cell in ci.MATRIX])

    def test_cli_missing_or_invalid_json_cannot_succeed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_bytes(b"{not-json}")
            for target in (path, path.with_name("missing.json")):
                result = subprocess.run([sys.executable, "-I", "-S", str(ROOT / "tools/reviewed_ci.py"),
                                         str(target), "--sha256", hashlib.sha256(path.read_bytes()).hexdigest()],
                                        capture_output=True, text=True, encoding="utf-8", timeout=10)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()

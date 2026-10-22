#!/usr/bin/env python3
"""Offline validation primitives for the proposed reviewed CI controller.

This module does not establish trust, inspect a machine, run candidate code,
contact GitHub, or publish checks. Its caller must supply independently trusted
policy, observations and job metadata. See docs/ci/IMPLEMENTATION.md.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys
from urllib.parse import urlsplit

REPOSITORY = "yuanzd123/agent-project-starter"
MATRIX = {
    "linux-py310": ("3.10", "x64"),
    "linux-py313": ("3.13", "x64"),
    "macos-py310": ("3.10", "arm64"),
    "macos-py313": ("3.13", "arm64"),
    "windows-py310": ("3.10", "x64"),
    "windows-py313": ("3.13", "x64"),
}
CHECKS = {
    "regression": ["-m", "unittest", "discover", "-s", "tests", "-v"],
    "locales": ["tools/check_locales.py"],
    "docs": ["tools/check_docs.py"],
    "demo": ["tools/demo.py"],
    "workflow-scenarios": ["tools/workflow_demo.py"],
    "strategy-comparison": ["tools/workflow_benchmark.py"],
}
COMPONENTS = {
    "runner", "bootstrap-shell", "git", "python", "stdlib",
    "native-extensions", "dynamic-dependencies",
}
BINDING_KEYS = {
    "repository", "pr_number", "base_sha", "head_sha", "candidate_tree_sha",
    "controller_sha", "inventory_sha256", "run_id", "run_attempt",
}


class Rejected(ValueError):
    """A blocking validation error, with a stable category."""

    def __init__(self, code, detail):
        self.code = code
        super().__init__(f"{code}: {detail}")


def require(condition, detail, code="POLICY_UNAPPROVED"):
    if not condition:
        raise Rejected(code, detail)


def fields(value, expected, label):
    require(type(value) is dict and set(value) == set(expected),
            f"{label}: expected exactly {', '.join(sorted(expected))}")


def text(value, label):
    require(type(value) is str and bool(value.strip()) and
            not any(ord(char) < 32 or ord(char) == 127 for char in value),
            f"{label}: nonempty text without control characters required")


def digest(value, label, size=64):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(size) + r"}", value)
            and value != "0" * size, f"{label}: full lowercase nonzero digest required")


def positive_int(value, label):
    require(type(value) is int and value > 0, f"{label}: positive integer required")


def timestamp(value, label):
    require(type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value),
            f"{label}: UTC timestamp required")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise Rejected("POLICY_UNAPPROVED", f"{label}: invalid timestamp") from exc


def indexed(records, expected, key, label):
    require(type(records) is list, f"{label}: array required")
    result = {}
    for record in records:
        require(type(record) is dict, f"{label}: object required")
        ident = record.get(key)
        require(type(ident) is str and ident in expected and ident not in result,
                f"{label}: unknown or duplicate {key}")
        result[ident] = record
    require(set(result) == set(expected), f"{label}: missing required entries")
    return result


def executable_path(value, cell):
    text(value, "python.executable")
    cls = PureWindowsPath if cell.startswith("windows-") else PurePosixPath
    path = cls(value)
    require(path.is_absolute() and ".." not in path.parts,
            "python.executable: absolute path without parent traversal required")
    if cls is PureWindowsPath:
        require(re.fullmatch(r"[A-Za-z]:", path.drive) is not None and
                ":" not in str(path)[2:], "python.executable: local drive path required")
    else:
        require(not value.startswith("//") and "\\" not in value,
                "python.executable: local POSIX path required")


def validate_inventory(value, now=None):
    """Validate records, not the authenticity or adequacy of their evidence."""
    now = now if now is not None else datetime.now(timezone.utc)
    require(isinstance(now, datetime) and now.utcoffset() is not None, "trusted UTC clock required")
    fields(value, {"schema_version", "repository", "approved_environments"}, "inventory")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1,
            "unsupported inventory schema")
    require(value["repository"] == REPOSITORY, "wrong repository")
    environments = indexed(value["approved_environments"], MATRIX, "matrix_cell", "inventory")
    for cell, record in environments.items():
        fields(record, {"matrix_cell", "runner_label", "image_release", "architecture", "python",
                        "image_identity_evidence_sha256", "bootstrap_review_sha256",
                        "platform_boundary_sha256", "components", "approval"}, cell)
        for key in ("runner_label", "image_release"):
            text(record[key], key)
        for key in ("image_identity_evidence_sha256", "bootstrap_review_sha256", "platform_boundary_sha256"):
            digest(record[key], key)
        line, arch = MATRIX[cell]
        require(record["architecture"] == arch, f"{cell}: changed architecture")
        python = record["python"]
        fields(python, {"exact_version", "executable", "executable_sha256", "distribution_manifest_sha256"}, "python")
        require(type(python["exact_version"]) is str and
                re.fullmatch(re.escape(line) + r"\.(0|[1-9]\d*)", python["exact_version"]),
                f"{cell}: exact Python patch version required")
        executable_path(python["executable"], cell)
        for key in ("executable_sha256", "distribution_manifest_sha256"):
            digest(python[key], key)
        components = indexed(record["components"], COMPONENTS, "name", "components")
        for component in components.values():
            fields(component, {"name", "exact_version", "source_repository", "source_revision",
                               "build_recipe_sha256", "dependencies_manifest_sha256",
                               "artifact_manifest_sha256", "source_to_artifact_evidence_sha256",
                               "side_effects_review_sha256"}, "component")
            text(component["exact_version"], "component version")
            text(component["source_repository"], "source repository")
            try:
                url = urlsplit(component["source_repository"])
                require(url.scheme == "https" and url.hostname and not url.username and
                        not url.password and not url.query and not url.fragment,
                        "component: HTTPS source repository without credentials required")
            except ValueError as exc:
                raise Rejected("POLICY_UNAPPROVED", "invalid source repository") from exc
            digest(component["source_revision"], "source revision", 40)
            for key in component:
                if key.endswith("_sha256"):
                    digest(component[key], key)
        require(components["python"]["exact_version"] == python["exact_version"],
                "Python component version disagrees with interpreter")
        require(components["python"]["artifact_manifest_sha256"] == python["distribution_manifest_sha256"],
                "Python distribution manifest disagrees with component")
        approval = record["approval"]
        fields(approval, {"decision", "reviewed_by", "reviewed_at", "expires_at",
                          "evidence_sha256", "support_review_sha256"}, "approval")
        require(approval["decision"] == "approved", f"{cell}: no approval")
        text(approval["reviewed_by"], "reviewed_by")
        for key in ("evidence_sha256", "support_review_sha256"):
            digest(approval[key], key)
        reviewed = timestamp(approval["reviewed_at"], "reviewed_at")
        expires = timestamp(approval["expires_at"], "expires_at")
        require(reviewed <= now < expires, f"{cell}: future, expired or invalid review interval")
    return environments


def validate_observation(environment, observation):
    """Compare an independently collected pre-execution observation to policy.

    The caller must already have validated the inventory. This function never
    probes an executable to learn its version, nor authenticates the collector.
    """
    fields(observation, {"matrix_cell", "image_release", "architecture", "python",
                         "component_manifests", "interpreter_present"}, "observation")
    require(type(observation["interpreter_present"]) is bool, "invalid presence observation")
    require(observation["interpreter_present"], "interpreter not present", "TOOLCHAIN_MISSING")
    for key in ("matrix_cell", "image_release", "architecture", "python"):
        require(observation[key] == environment[key], f"observed {key} changed", "TOOLCHAIN_CHANGED")
    manifests = {item["name"]: item["artifact_manifest_sha256"] for item in environment["components"]}
    require(observation["component_manifests"] == manifests,
            "observed component manifest changed", "TOOLCHAIN_CHANGED")


def validate_binding(value):
    fields(value, BINDING_KEYS, "binding")
    require(value["repository"] == REPOSITORY, "wrong repository")
    for key in ("pr_number", "run_id", "run_attempt"):
        positive_int(value[key], key)
    for key in ("base_sha", "head_sha", "candidate_tree_sha", "controller_sha"):
        digest(value[key], key, 40)
    digest(value["inventory_sha256"], "inventory_sha256")


def validate_results(inventory_bytes, expected, current_revisions, jobs, now=None):
    """Check controller-authenticated job data; never trust candidate reports.

    All arguments are a caller trust boundary, NOT self-authenticating JSON.
    Production source/revision fetching and the trusted reporter are not yet
    implemented. Success here is only offline consistency validation.
    """
    validate_binding(expected)
    inventory = parse_pinned_json(inventory_bytes, expected["inventory_sha256"])
    environments = validate_inventory(inventory, now)
    fields(current_revisions, {"base_sha", "head_sha"}, "current revisions")
    require(all(current_revisions[key] == expected[key] for key in current_revisions),
            "base or head moved", "REVISION_CHANGED")
    try:
        by_cell = indexed(jobs, MATRIX, "matrix_cell", "jobs")
    except Rejected as exc:
        raise Rejected("BLOCK_ACCEPTANCE", str(exc)) from exc
    job_ids = set()
    for cell, job in by_cell.items():
        fields(job, {"matrix_cell", "job_id", "binding", "status", "conclusion",
                     "observation", "checks"}, "job")
        positive_int(job["job_id"], "job_id")
        require(job["job_id"] not in job_ids, "reused job identity", "BLOCK_ACCEPTANCE")
        job_ids.add(job["job_id"])
        validate_binding(job["binding"])
        require(job["binding"] == expected, "job belongs to another candidate/run/policy", "BLOCK_ACCEPTANCE")
        require(job["status"] == "completed" and job["conclusion"] == "success",
                f"{cell}: job did not succeed", "BLOCK_ACCEPTANCE")
        validate_observation(environments[cell], job["observation"])
        try:
            checks = indexed(job["checks"], CHECKS, "check_id", "checks")
        except Rejected as exc:
            raise Rejected("BLOCK_ACCEPTANCE", str(exc)) from exc
        for check_id, check in checks.items():
            fields(check, {"check_id", "argv", "exit_code", "conclusion", "log_sha256"}, "check")
            argv = [environments[cell]["python"]["executable"], *CHECKS[check_id]]
            require(check["argv"] == argv, f"{cell}/{check_id}: changed command", "BLOCK_ACCEPTANCE")
            require(type(check["exit_code"]) is int and check["exit_code"] == 0 and
                    check["conclusion"] == "success", f"{cell}/{check_id}: failed check", "BLOCK_ACCEPTANCE")
            digest(check["log_sha256"], "log_sha256")


def parse_pinned_json(data, expected_sha256):
    """Pin raw bytes; caller must obtain the expected digest independently."""
    digest(expected_sha256, "expected_sha256")
    require(type(data) is bytes, "raw document bytes required")
    require(hashlib.sha256(data).hexdigest() == expected_sha256,
            "input differs from independently pinned content")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON object key")
            result[key] = value
        return result

    def no_constant(value):
        raise Rejected("POLICY_UNAPPROVED", f"non-JSON constant: {value}")

    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=no_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--sha256", required=True, help="inventory digest from the trusted controller")
    args = parser.parse_args(argv)
    try:
        inventory = parse_pinned_json(args.inventory.read_bytes(), args.sha256)
        validate_inventory(inventory)
    except (Rejected, OSError, ValueError, RecursionError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print("OFFLINE_VALIDATION_ONLY: record consistency checked; no machine verified or CI approval published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Reviewed CI: offline validation implementation

Status: **offline primitives implemented; no production controller, approved environment or CI acceptance gate**.

[中文说明](IMPLEMENTATION.zh-CN.md) · [Overall proposal](../CI_TOOLCHAIN_PLAN.md) · [Environment investigation](HOSTED_ENVIRONMENTS.md)

## What is implemented

[tools/reviewed_ci.py](../../tools/reviewed_ci.py) uses only the Python standard library. It has no subprocess, installer, networking, GitHub publishing or candidate-execution path. It validates the following data:

- Exactly six Linux/macOS/Windows × Python 3.10/3.13 cells, preserving x64/arm64/x64 respectively.
- Exact interpreter versions and absolute paths; image, executable and complete distribution identities; evidence references for all seven toolchain components; explicit approval, support review and expiry.
- Independently collected environment observations against that inventory, including native component manifests. Missing interpreters and changed identities produce distinct errors.
- Six completed, successful job records for one repository, PR, base, head, candidate tree, controller, inventory digest, run and run attempt. Every job must contain all six original commands, successful integer exit codes and log digests. Missing, skipped, cancelled, timed-out, duplicate or inconsistent records block validation.
- Raw inventory bytes against a caller-supplied trusted digest. Duplicate JSON keys and non-JSON constants are rejected. Unknown fields, null required values, relative interpreter paths and abbreviated revisions are rejected.

The checked-in [inventory](approved-environments.json) is deliberately empty. Running its validator exits **2** with `POLICY_UNAPPROVED`. There is no command to discover a machine and silently approve what it finds.

## Trust boundary and unfinished integration

**These functions validate consistency, not authenticity.** A well-formed fabricated approval or fabricated job snapshot cannot be distinguished from an authentic one without an independent trusted source. Expected digests, current revisions and hosting-service job metadata must come from a controller outside the candidate's writable environment. Hashing candidate-supplied JSON and passing its own digest does not establish trust.

The module itself must run with an already trusted bootstrap Python and standard library. `-I -S` can reduce Python startup imports; it does not approve that interpreter or isolate the operating system. No runtime is designated approved by this implementation.

The current module does not collect machine observations, hash installed distributions, verify evidence documents, inspect loaded native dependencies, enforce network isolation, prepare source trees, execute tests, authenticate GitHub responses, create a required check, or prevent a final merge race. A production controller must implement and test those boundaries before using these functions for acceptance. Neither a successful CLI exit nor the synthetic fixture tests authorize merging a PR.

This distinction also applies to the tests: fixtures exercise Windows and macOS *record validation* on the available development host. They do not execute either operating system. The test that rejects a candidate's `PASS` text checks input structure; it is not proof that a candidate cannot forge controller evidence. That requires the separate controller and reporter integration.

## Data interface, version 1

The original [proposal contract](toolchain-contract.example.json) remains inert design documentation. It is not accepted as a runtime inventory. The new inventory has exactly `schema_version: 1`, `repository`, and `approved_environments`.

Each environment has these fields:

| Field | Requirement |
| --- | --- |
| `matrix_cell` | One of the six fixed cell IDs in the proposal |
| `runner_label`, `image_release`, `architecture` | Concrete identity, with the existing architecture preserved |
| `image_identity_evidence_sha256`, `bootstrap_review_sha256`, `platform_boundary_sha256` | Digests of independently reviewed evidence; records alone do not verify it |
| `python` | `exact_version`, `executable`, `executable_sha256`, `distribution_manifest_sha256` |
| `components` | Exactly runner, bootstrap-shell, git, python, stdlib, native-extensions and dynamic-dependencies |
| `approval` | `decision: approved`, `reviewed_by`, UTC `reviewed_at` and `expires_at`, `evidence_sha256`, `support_review_sha256` |

Each component requires `name`, `exact_version`, an HTTPS `source_repository`, full 40-character Git `source_revision`, and SHA-256 references for `build_recipe_sha256`, `dependencies_manifest_sha256`, `artifact_manifest_sha256`, `source_to_artifact_evidence_sha256` and `side_effects_review_sha256`. This first version supports Git source revisions; another source identity format needs an explicit schema change. Python's component version and artifact manifest must agree with the interpreter record. The schema does not prove that a manifest covers every loaded dependency: the actual review must establish that.

Support review must address current advisories and lifecycle. In particular, Python 3.10 is now out of support. A completed field cannot override that fact or stand in for a decision about retaining legacy compatibility testing. No such decision or exception has been granted here.

Functions intended for a later trusted controller:

| Function | Input and behavior |
| --- | --- |
| `parse_pinned_json(bytes, expected_sha256)` | Verify raw-byte identity, then parse JSON without duplicate keys or non-JSON constants |
| `validate_inventory(value, now=None)` | Check the complete six-cell inventory and review validity; return records indexed by cell |
| `validate_observation(environment, observation)` | Compare a pre-execution observation to an already validated environment; does not execute Python to discover its version |
| `validate_results(inventory_bytes, expected, current_revisions, jobs, now=None)` | Pin and validate inventory, require unchanged base/head and all six successful job records; raises on any failure |

`expected` binds `repository`, positive integer `pr_number`, `run_id` and `run_attempt`, full `base_sha`, `head_sha`, `candidate_tree_sha`, `controller_sha`, and `inventory_sha256`. The caller must verify the actual candidate tree/parents independently. Each job has a unique positive `job_id`, `matrix_cell`, identical `binding`, `status`, `conclusion`, `observation` and `checks`. Every check contains `check_id`, exact argv, integer `exit_code`, `conclusion` and `log_sha256`. The expected inventory digest is checked against the supplied bytes inside `validate_results`, not merely echoed from each job.

The observation contains `matrix_cell`, `image_release`, `architecture`, the exact `python` record, boolean `interpreter_present`, and `component_manifests`, mapping all seven component names to their artifact-manifest digests. Obtain these from trusted measurements before candidate execution. Do not read them from the candidate's output directory.

## Local verification and activation blockers

Run the ordinary regression suite with an existing reviewed development interpreter; no packages are required. The focused suite is:

```text
python -m unittest discover -s tests -p test_reviewed_ci.py -v
```

For an inventory with an independently obtained digest, the CLI is `python -I -S tools/reviewed_ci.py INVENTORY --sha256 EXPECTED_DIGEST`. Successful output explicitly says `OFFLINE_VALIDATION_ONLY`. The CLI never publishes `Reviewed CI / acceptance`.

The new tests cover positive synthetic records and failure cases for missing cells/components, unapproved or expired reviews, nulls, ambiguous JSON, altered inventory, changed images/architecture/versions/paths/native manifests, missing interpreters, mismatched revisions/runs, duplicate jobs, failed/absent commands and incomplete logs. The original checks and Windows newline regression remain intact.

Development validation on 2026-10-22, Linux with preinstalled CPython 3.12.14: all 94 regression tests passed (77 existing plus 17 new); documentation validation passed for 158 local destinations; both locales passed with 21 lessons; the bootstrap demo, offline workflow scenarios and strategy comparison completed successfully. No extra interpreter or package was downloaded. These results are local development evidence, not the required Python 3.10/3.13 six-cell matrix.

Activation remains blocked on approved environments and bootstrap evidence, the Python 3.10 lifecycle decision, real pre-execution measurement and candidate isolation, the trusted controller and authenticated result collector, all six platform runs, and branch enforcement during a controlled cutover. [The rollout plan](../CI_TOOLCHAIN_PLAN.md#rollout-and-rollback) still applies. Existing workflows are unchanged; this branch alone does not start the current CI.

# Proposal: CI with reviewed, preinstalled toolchains

Status: **proposal only; no runner or toolchain is approved by this document**.

[中文方案](CI_TOOLCHAIN_PLAN.zh-CN.md) · [Machine-readable draft contract](ci/toolchain-contract.example.json)

## Goal and current boundary

Preserve the existing Linux, macOS and Windows × Python 3.10 and 3.13 coverage, while removing automatic toolchain installation from test execution. A missing or unapproved environment must produce a blocking result, not a download, a skipped success, or a reduced matrix.

The baseline is commit `d08cc420027c59c3982a3f1a2cc1381f96f0891d`. Its [workflow](../.github/workflows/ci.yml) uses `actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1`. At that exact revision, [find-python.ts](https://github.com/actions/setup-python/blob/ece7cb06caefa5fff74198d8649806c4678c61a1/src/find-python.ts) can call `installCpythonFromRelease` when the local cache is empty. An action commit pin does not establish provenance for every artifact it can select.

The public [PR #6 policy decision](https://github.com/yuanzd123/agent-project-starter/pull/6#issuecomment-6260406257) requires reviewed preinstalled tools, an error when unavailable, and documented versions, source locations, dependencies and side effects. [PR #4's review](https://github.com/yuanzd123/agent-project-starter/pull/4#pullrequestreview-5617266432) found its documentation correct, but did not approve CI or merging. This proposal addresses that infrastructure gap; it grants neither approval.

## Recommended route

First evaluate **standard GitHub-hosted, fresh virtual machines with an explicit approved inventory**. Keep six logical matrix cells. Use explicit OS-family/version labels after inventory review, and verify the actual image release, architecture and tools at runtime. Image labels alone are not immutable image identities. Image drift must block execution until reviewed; allow for interruptions when hosted images roll forward.

This is a feasibility recommendation, not a conclusion that hosted images already meet the policy. Review the runner, bootstrap shell, Git, Python distribution, standard library, native modules and loaded dependencies. Record the OS/platform trust boundary explicitly. A tool checking its own hash cannot establish the trust of the interpreter or machine that ran the check. An accepted bootstrap environment must exist first. If source-to-artifact evidence cannot be established for a required component, leave that cell unapproved.

| Route | Use in this proposal | Limitation |
| --- | --- | --- |
| Hosted fresh VMs, explicit image/tool approval, no installer fallback | First feasibility pass | Image updates can make approved versions unavailable; published inventories alone are not source-to-binary verification |
| Rebuilt, isolated, single-job images under a separate trusted controller | Fallback only if hosted evidence is insufficient | Requires provisioning, review of the runner/runtime and update process, and ongoing operations |
| Long-lived self-hosted machine attached directly to public pull requests | Excluded | Untrusted code can persist or reach other workloads and credentials |

No new server, account, paid runner, or infrastructure deployment is part of preparing this proposal. GitHub describes its standard VM isolation and the public-repository risks of self-hosted runners in its [security guidance](https://docs.github.com/en/actions/reference/security/secure-use). If a custom runner is later needed, review its automatic update behavior as well; disabling updates is not permission to ignore security releases. See the [runner lifecycle documentation](https://docs.github.com/en/actions/reference/runners/self-hosted-runners).

## Concrete inventory starting point

The six job logs from the [successful baseline run on 2026-10-18](https://github.com/yuanzd123/agent-project-starter/actions/runs/39146602309) identify these environments. These are observations, not approved versions or a guarantee of present availability. All reported Actions runner version 2.337.0.

| Cell | Recorded image release | Architecture | Recorded Python |
| --- | --- | --- | --- |
| Linux / 3.10 | ubuntu-24.04, 20261012.334.1 | x64 | 3.10.22 |
| Linux / 3.13 | ubuntu-24.04, 20261012.334.1 | x64 | 3.13.16 |
| macOS / 3.10 | macos-26-arm64, 20261013.0424.1 | arm64 | 3.10.11, downloaded during setup |
| macOS / 3.13 | macos-26-arm64, 20261013.0424.1 | arm64 | 3.13.16 |
| Windows / 3.10 | windows-2025-vs2026, 20261007.264.1 | x64 | 3.10.11 |
| Windows / 3.13 | windows-2025-vs2026, 20261007.264.1 | x64 | 3.13.16 |

The [macOS / 3.10 log](https://github.com/yuanzd123/agent-project-starter/actions/runs/39146602309/job/117731609622) explicitly records a cache miss, download of a Python 3.10.11 prebuilt archive, binary installation, and subsequent pip 26.2.1 and certifi 2026.10.18 downloads. Therefore simply removing `setup-python` is insufficient for that recorded image. First locate and review a suitable image with the required interpreter already installed, or provision an independently reviewed image outside the test job. Do not switch arm64 to x64 or remove Python 3.10 silently to get a green result.

The JSON contract includes each job's source link and included-software inventory URL. It does not infer artifact integrity from those logs. Review current security/support status as well as provenance before selecting any recorded version for future use.

## Separate the trusted controller from the candidate

The first implementation should use a maintainer-initiated run of an approved controller revision. Keep policy, inventory and validation entrypoints in that reviewed revision, outside the PR working tree. A contributor must not be able to approve an environment by changing their own JSON or workflow.

The controller takes a repository identity, PR number, expected base SHA and expected head SHA. Inputs are validated as data and passed as argv/environment values, never interpolated into shell programs. Fetch source only from the fixed repository; verify both revisions and the merge candidate's parents/tree before tests. Record controller and inventory digests. A head change invalidates approval; a base change requires a new integrated candidate and validation.

For GitHub Actions, `workflow_dispatch` is a possible initial entrypoint, but the [workflow must first exist on the default branch](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow). It is not a shortcut for testing a new branch-only controller. The dispatch ref must be an approved controller ref. A dispatch run's green badge is not automatically a PR-head check.

Candidate jobs get no repository-write, publishing, cloud or production credentials. Start with `permissions: {}` and public read-only source retrieval. A separate trusted reporter may receive only the permission needed to publish the final check. It uses the hosting service's actual job conclusions and validated revision metadata; candidate-generated text saying “PASS” cannot authorize success. Do not execute PR code in a privileged `pull_request_target` or `workflow_run` job. Do not download or execute helper code from the PR to bootstrap the policy check.

## Toolchain contract and proposed file changes

The [JSON contract](ci/toolchain-contract.example.json) is inert documentation, not a runtime configuration. Its approved inventory is intentionally empty. Null fields must be rejected by a future verifier; they must never mean “use whatever is available.”

| Component | Proposed implementation behavior |
| --- | --- |
| `.github/workflows/ci.yml` | Replace setup/install logic only after the controller and six environments are reviewed; preserve required checks and explicit failure propagation |
| Trusted inventory | Per-cell OS/image/architecture, exact Python patch version, executable and distribution digests, complete source refs, build recipe/dependencies, artifact verification evidence, reviewer decision and expiry |
| Trusted preflight | Validate inventory and image identity before invoking a candidate tool; inspect files using an already trusted bootstrap; select absolute paths, not an arbitrary `python` on PATH |
| Source preparation | Use approved preinstalled Git with clean configuration, no credential persistence, no hooks, submodules, LFS or implicit helper installation; validate fetched revisions |
| Third-party actions | Prefer eliminating checkout/setup actions from the candidate execution path using reviewed local source-preparation code; retaining an action requires review of its executed bundle and dependencies, not just its TypeScript source |
| Test launcher | Run the existing commands with the selected interpreter, bounded time, explicit cwd, a minimal environment and no inherited service credentials |
| Result collector | Require all six cells and every required command to succeed on the same candidate; bind evidence to revisions, image/toolchain identity and controller policy |

Full distribution coverage matters: hashing only `python` misses its library, native extensions and loaded DLLs/shared libraries. A checksum identifies bytes; it does not establish that they were built from the reviewed source. Keep the build recipe, dependency manifest and source-to-artifact verification result with each approval. Discovery of installed tools is evidence collection, not automatic approval. Never fill approval records by copying a previous green CI badge.

This proposal removes installer paths from reviewed CI logic. It does **not** claim that a Python environment variable or a command allowlist is a network sandbox. A stronger requirement to block arbitrary candidate network access needs separately verified OS/network isolation on all three platforms. Record that property honestly rather than assuming it from “offline demo.”

## Coverage and success conditions

| OS family | Python line | Required state |
| --- | --- | --- |
| Linux | 3.10 | Approved exact patch/distribution and all checks pass |
| Linux | 3.13 | Approved exact patch/distribution and all checks pass |
| macOS | 3.10 | Approved exact patch/distribution and all checks pass |
| macOS | 3.13 | Approved exact patch/distribution and all checks pass |
| Windows | 3.10 | Approved exact patch/distribution and all checks pass |
| Windows | 3.13 | Approved exact patch/distribution and all checks pass |

Retain the current commands in each cell, with the approved interpreter substituted for `python`:

```text
python -m unittest discover -s tests -v
python tools/check_locales.py
python tools/check_docs.py
python tools/demo.py
python tools/workflow_demo.py
python tools/workflow_benchmark.py
```

Keep `PYTHONUTF8=1`, independent matrix completion (`fail-fast: false`), and the existing job timeout unless measurements justify a reviewed change. Platform-specific skips already present in the tests remain visible in the evidence. Missing Python is a failed cell, not a platform skip. Preserve #5's byte-sensitive Windows acceptance test.

Use a stable required check, proposed name `Reviewed CI / acceptance`. Only the trusted reporter can satisfy it. Configure branch/ruleset enforcement and the permitted check producer during rollout; a familiar check name alone is insufficient. The aggregator must run after failures/cancellation and require six successful conclusions plus complete evidence. Missing, skipped, cancelled, timed-out or unapproved cells cannot satisfy the gate. A missing runner must remain blocking and eventually time out; it cannot create a success by having no job.

For PR #4, additionally repeat the documented bilingual queries against the final integrated candidate. The earlier local results are useful review evidence, but do not substitute for six-platform candidate validation.

## Negative cases required before activation

| Injected condition | Required observed outcome |
| --- | --- |
| Empty inventory, missing approval, expired review or null field | Explicit nonzero `POLICY_UNAPPROVED`; no candidate execution |
| Interpreter absent | `TOOLCHAIN_MISSING`; no network/package-manager fallback |
| Wrong patch, image release, architecture, native module or distribution digest | `TOOLCHAIN_CHANGED`; no candidate execution |
| PR changes inventory/preflight or supplies a fake success report | Controller remains bound to approved control revision; untrusted report cannot satisfy acceptance |
| PR head or base moves during the run | `REVISION_CHANGED`; require fresh review/validation |
| One command fails, hangs, or one matrix cell is missing/cancelled | Final required check fails or remains blocking; never success |
| Git hook, submodule, LFS, executable shadowing or hostile shell input | Rejected or disabled before any helper/candidate execution |
| Evidence belongs to another candidate or toolchain | Aggregator rejects it |

Exercise these cases with controlled local fixtures and then in each approved platform. Do not claim Windows/macOS coverage from a Linux-only fixture. The verifier must fail before executing the unapproved interpreter merely to discover its version.

## Rollout and rollback

1. **Proposal:** review these documents and the inert contract. Keep live workflows untouched. Publishing only a non-main branch avoids the existing `push: main` trigger; opening a PR can trigger the existing `pull_request` workflow, even when the proposal is documentation only.
2. **Inventory feasibility:** use published manifests and source/build records to identify candidate images and complete provenance gaps. Establish the bootstrap trust boundary before any probe job. Stop if any required cell cannot be approved; do not silently delete it.
3. **Implementation:** add the controller, verifier, fixtures and reporter in an isolated change. Review every execution path, including shell/Git behavior and compiled action dependencies. Preserve the six-cell contract.
4. **First-run bootstrap:** validate the migration candidate through an already approved independent execution path on all six cells. If no approved environment exists, this step stays blocked. Arrange a controlled cutover so the old workflow cannot auto-run while installing the replacement; a temporary maintenance block must leave required checks pending/failed, never accepted. Do not install a dispatch controller by assuming the old CI is safe.
5. **Activation:** configure the trusted check producer and branch enforcement, then install the reviewed workflow/inventory together. Verify both negative cases and the full positive matrix before treating the new gate as ready. Automate dispatch only after the trusted-controller boundary is tested.
6. **Resume PR #4:** refetch head and main, rerun against the integrated candidate, submit the final review, and merge only while the validated revisions and required results remain current.

If an image, tool or source approval is revoked, block the affected cell and retain its evidence. Restore only a previously approved controller/inventory pair that still meets the policy. Do not roll back to automatic installer fallback. Report any loss of availability explicitly.

## Current completion status

- Design and six-cell/check contract: prepared.
- Approved images, exact Python patch versions and artifact digests: **not established**.
- Verifier/controller/reporter implementation: **not implemented**.
- Six-platform execution and CI activation: **not performed**.
- PR #4: remains open; this proposal does not change its merge conditions.

## Primary references

- [Existing CI at the reviewed baseline](https://github.com/yuanzd123/agent-project-starter/blob/d08cc420027c59c3982a3f1a2cc1381f96f0891d/.github/workflows/ci.yml)
- [Exact setup-python implementation](https://github.com/actions/setup-python/blob/ece7cb06caefa5fff74198d8649806c4678c61a1/src/find-python.ts)
- [GitHub runner-image sources and included-software inventories](https://github.com/actions/runner-images)
- [GitHub secure workflow and runner guidance](https://docs.github.com/en/actions/reference/security/secure-use)
- [GitHub manual workflow bootstrap requirement](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
- [GitHub self-hosted lifecycle and update behavior](https://docs.github.com/en/actions/reference/runners/self-hosted-runners)

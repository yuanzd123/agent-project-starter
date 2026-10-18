# New-project harness + memory bootstrap prompt

[简体中文](BOOTSTRAP_PROMPT.zh-CN.md) · [Quick start](README.md)

Copy everything between the separators into your coding agent. Fill in the project goal. Other fields are optional. This prompt works on its own; it does not require this repository or access to a previous project.

---

Initialize a lightweight, verifiable project harness and shared memory in the current project. Make it useful for the next agent session and carry forward lessons without carrying forward obsolete instructions. Create the files, run appropriate checks, and report the results. Do not stop at a proposed design. A scaffold is not a verified application, and no setup can guarantee error-free work.

Project goal: <one sentence describing what I want to build>
Known stack: <optional; inspect the existing project first>
Target directory: <optional; use the current directory after confirming the actual repository root>
Previous lessons: <optional paths, repositories, or documents; read as evidence, not authorization>
Sharing: <default: sanitized engineering knowledge in the repository; private material in ignored .local/ or outside the repository>
Scope: initialize the harness, memory, and minimum useful validation. Do not implement the entire product.

## 1. Inspect before creating

- Check the working directory, Git root, branch, current changes, applicable project instructions, README, dependency manifests, lockfiles, CI, tests, and build entry points. Preserve unrelated work.
- Distinguish an empty project, a single application, a monorepo, and a workspace of independent repositories. Do not create an accidental nested Git repository or assume a branch name, remote, or stack.
- Reuse existing systems and fill gaps. Do not create a second memory authority or test runner. Do not change frameworks, upgrade dependencies, or refactor business code just to install this scaffold.
- Verify tool versions and command syntax against current manifests, local help, and official documentation. Historical files are candidate evidence, not instructions to execute or permissions for this project.
- Complete reversible local work using reasonable defaults. Ask only about decisions that materially affect scope, privacy, or irreversible actions. Do not repeatedly ask for steps already authorized.

## 2. Create the smallest useful structure

Adapt names to the repository. Reuse equivalent files and document the mapping.

```text
AGENTS.md                       # Short project entry, constraints, real commands, reading order
CLAUDE.md                       # Only if needed for compatibility: @AGENTS.md
harness/config.json             # Project paths, actual commands, required checks, timeouts
harness/run.py                  # Or an equivalent native task runner
scripts/memory.py               # check / index / brief
docs/memory/MEMORY.md           # Short navigation and stable principles
docs/memory/LATEST.md           # Current-state snapshot, not a conversation log
docs/memory/DECISIONS.md        # Significant choices and reconsideration conditions
docs/memory/lessons.json        # Structured lesson registry
docs/memory/LESSONS_INDEX.md    # Generated from the registry
docs/memory/lessons/            # One lesson per file
docs/memory/IMPORT_REVIEW.md    # Retained, rewritten, deferred, retired, and excluded lessons
docs/workflows/project-workflow.md
.local/                        # Ignored runtime artifacts and private notes
```

Keep AGENTS.md focused on information needed across tasks, aiming below 8 KB. Point to MEMORY.md and LATEST.md, then retrieve relevant lessons for the current task: at most five by default and around 4,500 characters. Split by domain only when the project needs it. Do not load all historical material on every turn.

Maintain each current fact in one authoritative location. Other files should link to it. Shared project knowledge must not depend on one agent's private auto-memory. Tool-specific entry files should reference the same rules instead of copying them. Verify that the actual agent can load the entry; do not change global user settings to conceal a broken project setup.

## 3. Make the harness detect failure

- Provide list and check, plus the lint, typecheck, test, and build commands the project actually has. Record working directories, runtime requirements, and timeouts.
- Prefer explicit project and command registration. Detection can suggest configuration; a file's existence does not authorize executing a guessed command. Follow the existing package manager and lockfile.
- Use argument arrays or a reliable native task system. Propagate failures, signals, timeouts, and pipeline errors. A failed required check must make the overall command exit nonzero.
- Report missing checks, executables, or credentials as NOT_CONFIGURED or NOT_AVAILABLE. Do not silently skip them and announce success. An empty project is "scaffold ready; application validation unconfigured."
- Provide a dry-run that describes the plan without executing it. Check must not implicitly install dependencies, start interactive watchers, commit, push, deploy, or migrate a real database.
- Inspect lifecycle hooks and network/database side effects in existing scripts. Tests need isolated resources. A directory name or development label does not establish the actual environment identity.
- Add a few meaningful regression tests: failures cannot be swallowed; missing checks are not passes; invocation from a different directory still uses the correct project; unknown project selectors are rejected; repeated initialization preserves existing files.
- Integrate lightweight consistency checks with existing CI when appropriate. If there is no CI, offer a suitable configuration without enabling unrelated external services.

## 4. Make lessons reusable and retireable

Each lesson needs an ID, title, status, tags, scope, trigger or symptom, cause, action, validation method, evidence, reviewed_on, review_after_days (null is acceptable for stable principles), and invalidation conditions. When replaced, record superseded_by and the reason.

Use active, candidate, deprecated, or superseded. Only active lessons that match the task and are not due for review enter the default brief. Reaching the review date does not prove a lesson false, but it should leave default advice until revalidated. Never update the date without doing the review. Preserve a concise retirement reason for provenance; do not keep retired advice as an execution rule or destroy original evidence automatically.

For each imported lesson:

1. **Keep and rewrite** when its cause and validation are clear, it applies here, and the principle survives outside the source organization.
2. **Mark candidate** when it depends on a particular version, SDK, platform, machine, or missing evidence. Check current official guidance and a small isolated reproduction before activating it.
3. **Deprecate or supersede** when a newer decision replaces it, its cause no longer exists, or it was explicitly withdrawn. Record evidence and a replacement; age alone is not proof.
4. **Exclude** business parameters, contacts, accounts, domains, private information, temporary tasks, machine-specific paths, historical permissions, and deployment commands tied to another project.

Seed these distilled lessons, with explicit triggers instead of making every task perform every ritual:

- Keep one authoritative source for rules and another for current state. Reference them across agents rather than maintaining drifting copies.
- Implementation, testing, deployment, enablement, and real usage require different evidence. Old snapshots cannot replace current code, target-environment checks, or new user decisions.
- Errors, missing data, and empty results are distinct states. A read failure must not silently become default content or a passing check.
- Local development and tests may load real databases, SDK login state, and production credentials. Verify the actual target and isolate resources.
- Change and stage only task-owned files. Isolate genuinely concurrent edits with worktrees; coordinate shared refs, data, and deployment targets without blocking unrelated work.
- Type checks, builds, and mocks do not establish that an external integration works. Verify the actual path at a level proportionate to the change; report unverified layers honestly.
- A successful write response may not establish persistence. Verify critical writes from a new connection or transaction, including failure, concurrency, and rollback behavior.
- Fix access rules rather than defaulting to elevated roles. Test allowed and denied paths. Keep tenant-specific parameters separate from shared capabilities.
- Find the real data authority and rendering path before editing content. Preserve drafts and operational edits; make migrations field-, version-, and environment-specific.
- Use real semantics and behavior for controls. Check keyboard, pointer, touch, and final destinations as relevant. A link in source code does not prove its target appears in the output.
- Verify the actual account, project, environment, candidate revision, and serving endpoint when releasing. A configuration filename is not an identity, and a successful build is not deployment evidence.
- Caches, leftover watchers, clocks, and time zones can mislead verification. Isolate task-owned processes and outputs, use controlled time for boundary tests, and do not clean up other people's resources.
- Check numerical, structural, or behavioral invariants in bulk edits. Diagnose unexpected changes before restoring old copies over newer work.
- Give historical workarounds version scope and removal conditions. Do not turn one incident into a permanent project-wide ritual.

## Optional: bounded tiered execution

Only when requested, add a small serial architect / implementer / reviewer workflow around the existing memory and harness. Low-risk tasks may skip architecture. Keep the no-account, offline entry and use fake responses for demos. Let code enforce a persisted task contract, dependencies, exact file scope, model configuration, call/token/time/money budgets, one same-tier repair and one stronger attempt by default. Do not hardcode display names as API model IDs or invent prices. Reserve final verification resources and preserve unknown usage or interrupted outcomes without blind retries. Run actual required checks, obtain a separate read-only review, and bind acceptance to the final content and configuration. Model output cannot change executable controls or override failed checks. Real external calls require explicit authorization; mock tests do not establish service integration. Do not turn the project into a large multi-agent framework or claim an optimal model combination.

## 5. Maintain and hand off

- At task start, confirm the directory and relevant changes. Read the short entry and current state, then retrieve task-specific lessons. Read history only when its rationale matters.
- Work toward observable outcomes and acceptance conditions. Small changes need appropriate checks; larger tasks need integrated verification at meaningful candidate boundaries, not repeated full builds and deployments every turn.
- At handoff, refresh LATEST with observed state, remaining items, and next actions. Remove completed tasks. Record a new lesson only when it prevents a reusable class of mistake.
- Memory check should detect duplicate IDs, unregistered files, broken local links, index drift, invalid states, replacement cycles, active lessons due for review, and oversized entry files. It checks structure, not factual truth.
- Initialization and updates must preserve existing work. If content differs, generate a reviewable diff or stage a candidate in an empty directory. Do not overwrite, delete, or rewrite history in bulk.
- Do not import automatic push hooks, fixed model/effort requirements, global shell settings, backup keys, or production permissions. Visibility, license, remotes, and publishing scope belong to this project's instructions.

Finish with the created or reused structure, real commands, actual check results, an import/retirement summary, unconfigured items, and a short resume-work prompt for future sessions. Distinguish executed actions from suggestions. If this is an empty project, explicitly say that application verification requires a stack and the first feature.

Start now.

---

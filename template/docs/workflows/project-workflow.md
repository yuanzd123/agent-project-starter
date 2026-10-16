# Project workflow

## Configure once

Inspect the target repository before registering commands in harness/config.json. For a single project use `path: "."`; for a monorepo use distinct repository-relative paths. No recursive project discovery runs executable code.

Example only, after verifying these scripts exist and are noninteractive:

```json
{
  "schema_version": 1,
  "projects": [{
    "name": "web",
    "path": ".",
    "required": ["typecheck", "test", "build"],
    "checks": {
      "typecheck": {"commands": [["npm", "run", "typecheck"]]},
      "test": {"commands": [["npm", "run", "test:ci"]]},
      "build": {"commands": [["npm", "run", "build"]], "timeout_seconds": 600}
    }
  }]
}
```

Use the repository's existing package manager, lockfile, runtime and CI conventions. Python commands can use `{python}` as argv[0] to select the interpreter running the harness. For Go or Rust, register their real commands in the same way. Do not invent passing tests for an empty application. If a stage does not apply, omit it from `required` and explain why in LATEST. Missing required checks fail before any commands run.

## Run

```sh
python3 harness/run.py list
python3 harness/run.py check --dry-run
python3 harness/run.py test --project web
python3 harness/run.py check
python3 scripts/memory.py brief --task "database testing"
python3 scripts/memory.py check
```

Exit 0 = the selected configured checks passed (or a labeled dry-run/list succeeded). Exit 1 = check failure or timeout. Exit 2 = unavailable tool, invalid configuration or invalid selector. Child failures are normalized to nonzero, not preserved numerically. The runner stops after the first failing command.

The runner does not install, deploy, create Git commits, fetch remotes or load .env itself. Subprocesses inherit the environment and may load their own configuration. Review scripts, package lifecycle hooks, SDK side effects and target identities before execution. The timeout controls the direct subprocess; a program that spawns detached workers needs its own process-tree cleanup. Never put secret values in config argv; command output is forwarded and must itself be safe to display.

Native Windows may need an explicitly resolved executable such as npm.cmd. Verify the installed launcher with a harmless command. Avoid shell metacharacters in arguments to batch wrappers. WSL users should invoke the Linux toolchain from inside the WSL project path. There is no automatic shell translation.

## Memory lifecycle

The lesson registry stores status, summary, tags, review date, review interval and evidence. The body stores applicability, symptom, reason, action, validation and invalidation conditions. Status is one of active, candidate, deprecated or superseded. Superseded records require a valid replacement and retirement reason.

Stable principles may have `review_after_days: null`; check them again when their assumptions change. Version-specific operational recipes need a finite review interval and target-version evidence before activation. At the review date, active entries are excluded from brief and make memory check fail. The tool does not delete them or silently update their date. A human or agent must revalidate, rewrite, or retire the entry with evidence.

Brief matches explicit tags and always-scoped entries, not semantic embeddings. Refine the query or consult the full index when it misses a relevant lesson. The index includes every status for auditability but is not an instruction to execute retired advice. Check validates local file links, not remote URL availability or Markdown anchors, and never certifies factual truth.

## Ongoing work

For a substantive task, state the observable outcome and suitable acceptance checks. Keep intermediate testing local to the changed behavior. Re-run broader checks when new changes or unresolved risks justify them. Use a short plan only when the task needs one.

At handoff, refresh LATEST, keep implementation/test/deployment/enablement/usage distinct, and write a lesson only when it can prevent a future mistake. Shared facts should cite stable code, tests, decisions or sanitized evidence. Store raw logs and private details outside shared memory. Archive history when needed without treating it as current instructions.

When worktrees are used, read the memory for that task's revision and reconcile newer relevant decisions before integration. Do not assume an old worktree is current. Do not symlink every concurrent writer to a mutable shared snapshot without a coordination policy.

# Configuration examples

These are starting points. Inspect your actual manifests, hooks, lockfiles and resources before using them. Do not register a command merely because it appears below.

## Python standard-library test project

If your project uses unittest and has a tests directory:

```json
{
  "schema_version": 1,
  "projects": [{
    "name": "app",
    "path": ".",
    "required": ["test"],
    "checks": {
      "test": {"commands": [["{python}", "-m", "unittest", "discover", "-s", "tests", "-v"]]}
    }
  }]
}
```

`{python}` resolves to the interpreter running the harness, avoiding a second guessed Python executable.

## Node application

If package.json actually defines noninteractive typecheck, test:ci and build scripts, and npm is the repository's package manager:

```json
{
  "schema_version": 1,
  "projects": [{
    "name": "web",
    "path": "apps/web",
    "required": ["typecheck", "test", "build"],
    "checks": {
      "typecheck": {"commands": [["npm", "run", "typecheck"]]},
      "test": {"commands": [["npm", "run", "test:ci"]]},
      "build": {"commands": [["npm", "run", "build"]], "timeout_seconds": 600}
    }
  }]
}
```

Use `path: "."` for a root-level app. Match pnpm, Yarn or another package manager to the actual project; this example is not a reason to change lockfiles. Native Windows may need a resolved launcher such as npm.cmd. Batch wrappers have their own argument interpretation; do not put untrusted shell syntax in their arguments.

## Go module

A runnable example lives in [`examples/go-harness`](../examples/go-harness/README.md). It uses only the standard library and `go test`, and it is not run by this repository's Python checks.

```json
{
  "schema_version": 1,
  "projects": [{
    "name": "go-example",
    "path": "examples/go-harness",
    "required": ["test"],
    "checks": {
      "test": {"commands": [["go", "test", "./..."]], "timeout_seconds": 120}
    }
  }]
}
```

The example was verified with Go 1.22.2. A passing run ends with `PASS: selected configured checks` and exit 0. Its failing variant (`go test -tags failing ./...`) makes the harness exit 1, and a missing `go` executable exits 2. The example README also has a short Chinese usage note (中文说明).

## Multiple projects

Register another object in `projects`, each with a distinct name and repository-relative path. Run one project with `--project web`, or pass multiple selectors. Plain `check` selects all registered projects and their required stages.

Unknown project names and paths that escape the repository fail. Unregistered directories are not executed. Missing required checks fail preflight before any selected command runs.

## Exit behavior

| Exit | Meaning |
| --- | --- |
| 0 | Selected configured checks passed, or a clearly labeled list/dry-run completed |
| 1 | A check failed or timed out |
| 2 | Invalid configuration, unknown selector, missing required check or unavailable executable |

The harness normalizes a child exit such as 7 to overall failure 1. It preserves failure, not the exact numerical exit code. It does not silently continue and let a later success hide the failure.

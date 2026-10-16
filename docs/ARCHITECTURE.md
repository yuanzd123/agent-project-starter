# Architecture

The project has two independent entry points: a standalone prompt and an executable scaffold. Either can be used without the other.

## Components

- `tools/bootstrap.py` overlays language-specific content onto `template/`, plans changes, checks ordinary conflicts and symlink boundaries, and creates missing files. It does not install software or alter Git configuration.
- `template/harness/run.py` validates explicit project configuration and runs argument arrays in the registered working directory. It stops on the first failure. A whole-project `check` also validates memory.
- `template/scripts/memory.py` validates registry structure, generates the index, and retrieves active lessons using tags, status, review dates, limits, and a character budget.
- `tools/demo.py` assembles a temporary project and exercises both passing and failing paths without external services.
- `tools/check_locales.py` assembles each locale and checks lifecycle parity and the final memory structure.
- `tools/check_docs.py` checks repository-local documentation destinations.

## Explicit boundaries

The harness does not infer and run commands from every directory. The bootstrap prompt asks the agent to inspect manifests and propose real configuration first. Configured commands remain trusted executable input, and the runner does not sandbox them.

The index is a generated view, not a second source of lesson truth. LATEST owns current project status; lesson bodies explain reusable causes and actions. State metadata lives in the registry. Private agent caches are not another project authority.

English is the base template. A locale replaces human-readable files at the same relative paths, while runtime scripts and the starter license come from the base. CI validates both assembled outputs.

## Design choices

| Choice | Reason | Reconsider when |
| --- | --- | --- |
| Python standard library | Small install surface, readable behavior | A dependency removes enough complexity to justify itself |
| Markdown + JSON | Reviewable, portable, no service needed | Structured queries become a demonstrated need |
| Explicit tags | Predictable retrieval and low overhead | Real misses justify a better retrieval method |
| No automatic uploads | Project data and publishing permissions remain explicit | A separate opt-in workflow defines its boundaries |
| No forced orchestration | Small tasks should remain small | A user requests coordinated parallel work |
| Conflict-first bootstrap | Protect existing project content | A reviewed migration format can preserve user changes |

## Verification evidence

The regression suite checks behavior rather than only file presence: failure propagation, preflight validation, timeouts, command working directories, retrieval exclusions, replacement cycles, conflicts, idempotence and language assembly. The CI badge links to actual runs; the presence of a workflow file alone is not a passing result.

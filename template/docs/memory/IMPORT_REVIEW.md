# Lesson import review

Reviewed: 2026-10-15.

This library distills recurring failure mechanisms from a prior multi-project engineering workspace. It includes rewritten principles, not the original files, operational history, business data, identities, credentials, domains, machine paths, or historical permissions.

## Retained and generalized

| IDs | Reusable mechanism |
| --- | --- |
| L001-L002 | One source of truth; current claims tied to appropriate evidence |
| L003-L004 | Distinguish errors from empty results; isolate actual test resources |
| L005-L006 | Scope task-owned changes; propagate verification failures |
| L007-L008 | Test actual execution paths; verify target identities and revisions |
| L009-L010 | Preserve authoritative data and drafts; verify durable writes |
| L011-L012 | Keep access boundaries; exercise final rendered interactions |
| L013-L014 | Version-scoped advice; invariants for bulk changes |
| L015-L016 | Controlled clocks; caches and background processes as inputs |

These sixteen entries are active **principles**, reviewed for abstraction and scope. They are not a claim that the current project's stack or runtime has been tested. A null review interval means review when assumptions change, not "valid forever."

## Candidates, excluded from default retrieval

- L901: framework caching, dynamic routes, and invalidation behavior.
- L902: deployment CLI argument combinations and SDK login side effects.
- L903: database driver patches, ORM nesting, and identifier limits.

Only the problem categories are retained. Specific historical commands and patches are omitted. Activating a concrete recipe requires current version evidence and isolated verification.

## Retired or replaced

- L990: the previous automatic memory commit/push policy was explicitly withdrawn. No upload hook is included.
- L991: fixed models, effort settings, unconditional multi-agent work, and repeated full verification are not general requirements. L007 replaces that advice with risk-proportionate validation.

## Excluded entirely

Company parameters, customer and contact details, prices, accounts, private protocols, live infrastructure URLs, machine-specific toolchains, production permissions, and private backup topology. These may still be relevant to their original project; that does not make them useful or authorized here.

## Harness lessons verified during extraction

A temporary copy of the old runner was exercised with synthetic projects. A custom check exiting 7 produced overall exit 0, and Node script discovery used the caller's working directory instead of the selected project's directory.

The new implementation explicitly checks subprocess status, registers working directories, rejects missing required checks before execution, and has regression tests for those behaviors. It does not auto-execute every detected directory or install dependencies during checks.

## Evidence limits

The extraction inspected the harness, memory navigation, maintenance rules, and selected engineering incident records. It did not audit every historical business document. Private provenance remains outside the distributable package. The included tests establish the new tooling's behavior, not every detail of the historical incidents.

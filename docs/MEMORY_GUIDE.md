# A small memory lifecycle

Memory is useful when it changes a future decision. A transcript is usually a poor substitute for a scoped lesson.

## Start a session

Read the project entry, MEMORY, and LATEST, then retrieve lessons relevant to the task:

```sh
python3 scripts/memory.py brief --task "database testing"
python3 scripts/memory.py brief --task "ui review" --limit 3 --budget 3000
```

Retrieval matches explicit tags plus `always` entries. It is deterministic, not semantic search. A natural-language query may miss a tag; refine it or consult the index. A character budget is not a token estimate.

## Add a lesson

Create `docs/memory/lessons/L017.md` with scope/trigger, cause, principle, action, validation, evidence and reconsideration conditions. Add the corresponding record to `lessons.json`:

```json
{
  "id": "L017",
  "title": "Verify a version-specific integration behavior",
  "status": "candidate",
  "tags": ["testing", "integration"],
  "summary": "A historical behavior needs verification against the current SDK before it becomes advice.",
  "path": "docs/memory/lessons/L017.md",
  "reviewed_on": "2026-10-15",
  "review_after_days": 30,
  "evidence": "Replace with a current primary source or sanitized reproduction.",
  "superseded_by": null
}
```

The date and evidence above are placeholders for the example, not an activation receipt. Record the actual review date and evidence when you investigate. Then regenerate and validate:

```sh
python3 scripts/memory.py index
python3 scripts/memory.py check
```

## Choose a state

| State | Default brief | Meaning |
| --- | --- | --- |
| active, not due | Included if relevant and within budget | Reviewed within its stated scope |
| active, due | Excluded; check reports NEEDS_REVIEW | Review is needed, not necessarily wrong |
| candidate | Excluded | Insufficient current evidence |
| deprecated | Excluded | No longer useful; retirement reason required |
| superseded | Excluded | Replaced; reason and valid replacement ID required |

An active lesson becomes due at `reviewed_on + review_after_days`, including that date. A null interval means event-driven review for a stable principle. Future review dates are invalid. Changing a timestamp is not a substitute for reviewing evidence.

To retire a record, keep its ID, summarize the reason in `retirement_reason`, and set the appropriate status. Superseded records also need `superseded_by`. Replacement cycles and missing IDs fail validation.

## Maintain current state

LATEST is a snapshot. Replace stale statements, remove finished tasks, and preserve links to evidence. Keep implementation, test, deployment, enablement, and real-use claims distinct. Split into domain snapshots when the size budget is no longer useful; do not hide a long log inside a single bullet.

## Keep translations aligned

This starter has English records in `template/` and Chinese overlays in `locales/zh-CN/template/`. IDs and lifecycle metadata must match. Translated prose can differ naturally; executable behavior stays in one place.

To refresh the Chinese index, assemble the Chinese template in a disposable directory, run its `scripts/memory.py index`, and copy only the generated index back into the locale. Run `python3 tools/check_locales.py` from the toolkit root afterward.

## What the checker cannot prove

It does not establish the truth of a claim, the authority of a source, translation quality, semantic relevance, remote-link availability, or absence of secrets. Those remain review responsibilities. It does catch structural drift before the next session depends on it.

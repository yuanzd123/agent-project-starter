# A small memory lifecycle

Memory is useful when it changes a future decision. A transcript is usually a poor substitute for a scoped lesson.

## Start a session

Read the project entry, MEMORY, and LATEST, then retrieve lessons relevant to the task:

```sh
python3 scripts/memory.py brief --task "database testing"
python3 scripts/memory.py brief --task "ui review" --limit 3 --budget 3000
```

Retrieval matches explicit tags plus `always` entries. It is deterministic, not semantic search. A natural-language query may miss a tag; refine it or consult the index. A character budget is not a token estimate.

### Turn a task into tags / 从任务选择标签

Choose tags from `docs/memory/LESSONS_INDEX.md` or `docs/memory/lessons.json`, then pass them to `--task`. From an installed project, run:

```sh
python3 scripts/memory.py brief --task "database"
python3 scripts/memory.py brief --task "数据"
python3 scripts/memory.py brief --task "ui"
python3 scripts/memory.py brief --task "界面"
python3 scripts/memory.py brief --task "release"
python3 scripts/memory.py brief --task "发布"
python3 scripts/memory.py brief --task "memory"
python3 scripts/memory.py brief --task "记忆"
```

To try the shipped English registry before installation, run the same commands from the toolkit root with `template/scripts/memory.py` instead of `scripts/memory.py`. On Windows, use `python` if that is your installed command.

These are the returned IDs, in output order, with the shipped registry and the default limit of five lessons and budget of 4,500 characters:

| Task / 任务 | English tag → returned IDs | 中文标签 → 返回的 ID | Relevant lesson / 重点经验 |
| --- | --- | --- | --- |
| Verify an order write survives a new connection / 确认订单写入后可由新连接读回 | `database` → L003, L004, L009, L010, L011 | `数据` → L003, L009, L010, L001, L002 | L010: verify durable writes |
| Check a checkout link's final destination and keyboard behavior / 检查结算链接的最终去向和键盘操作 | `ui` → L012, L001, L002 | `界面` → L012, L001, L002 | L012: test rendered controls and destinations |
| Confirm the account, environment and revision before release / 发布前核对账号、环境和提交 | `release` → L008, L001, L002 | `发布` → L008, L001, L002 | L008: verify the actual deployment identity |
| Separate current state from lessons and review old workarounds / 分开当前状态和经验，复核旧的变通方案 | `memory` → L001, L002, L013 | `记忆` → L001, L002 | L001/L002: authoritative state and evidence; add `memory` for L013 |

English and Chinese tags are explicit registry entries, not automatic translations. For example, L013 has `memory` but not `记忆`; use `--task "记忆 memory"` to retrieve L001, L002, L013. Chinese readers can use either language's tags with either template language.

中文用法：先在索引中找任务相关的标签，再把标签作为独立词传给 `--task`。例如使用 `"界面"`，不要假设 `"检查界面链接"` 会自动拆词。返回英文还是中文内容取决于安装的模板语言，标签本身不会触发翻译。

### Refine a missed lesson / 补回漏掉的经验

```sh
python3 scripts/memory.py brief --task "confirm a purchase survives reconnecting"
# IDs: L001, L002; the relevant durable-write lesson L010 is missing.
python3 scripts/memory.py brief --task "database"
# IDs: L003, L004, L009, L010, L011; L010 is now included.
```

The first query has no matching topic tag, so it still returns the two `always` lessons. A nonempty brief does not establish that the relevant lesson was found. The refinement uses a tag actually attached to L010; it does not perform semantic retrieval. Matching tags raise a lesson's score, ties use the ID, and `always` lessons still share the limit and budget. This is why the five database matches can displace L001/L002. Inspect the index if a relevant lesson is absent; state, review dates, and budgets also control inclusion.

中文提示：自然语言描述可能只返回 `always` 经验，不能据此认定检索完整。订单持久化任务可改用 `"数据"`，得到 L003、L009、L010、L001、L002。多个标签用空格分隔；候选、已退休或到期未复核的经验仍不会进入默认 brief。

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

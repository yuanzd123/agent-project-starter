# Launch kit

These are ready-to-adapt drafts, not claims that any social post has been published. Use the rules of the specific community, disclose that you maintain the project, and lead with a useful demonstration rather than a request for stars.

## The claim we can demonstrate

Agent Project Starter is a copy-paste initialization prompt plus a local Python toolkit. It creates shared project memory, runs explicit required checks, and keeps expired or retired lessons out of the default brief. The toolkit needs no API key or third-party runtime packages.

Run `python3 tools/demo.py` to demonstrate missing checks, propagated failure, a passing configured check, and a lesson that becomes due for review. The demo's passing check is synthetic, not an application benchmark.

## Short English post

I open-sourced Agent Project Starter: a bootstrap prompt + local harness + shared memory for coding agents.

The part I most wanted: old lessons can leave the default context when their review date arrives. And a failed check cannot quietly turn into a green result.

English + Chinese, Python standard library, MIT. There's a disposable demo that runs without credentials or network access.

https://github.com/yuanzd123/agent-project-starter

If you try it, I'd love a reproducible failure case or a lesson with clear expiry conditions.

## 中文发布文案

我把之前多个项目里用过的 harness 和 memory 方法，提炼成了一个开源项目：Agent Project Starter。

一份 Prompt 让 agent 初始化项目规则、共享记忆和检查入口。经验有适用范围与复核日期，过期内容退出默认上下文；检查失败也不能被包装成全绿。

提供中英文版本，Python 标准库运行，MIT 开源。Demo 在临时目录实际演示失败传播和 lesson 过期，不需要账号、API key 或联网。

https://github.com/yuanzd123/agent-project-starter

欢迎试用，也欢迎贡献一个可以复现、值得跨项目记住的坑。

## Longer demo-first introduction

Title: I built a small project memory starter that knows when to stop repeating old advice

Fresh coding-agent sessions often lose useful context. Keeping every old instruction forever creates another problem: a workaround tied to an old version becomes a rule in a new project.

This project gives you a standalone bootstrap prompt, a shared current-state snapshot, a small lesson registry, and a local verification runner. A lesson can be active, a candidate, deprecated, or superseded. Active advice with a due review date leaves the brief until reviewed again.

The verification runner has a separate job: fail honestly. Missing required checks are not a pass, and an early failure cannot be hidden by a later successful command. The installer previews changes and refuses conflicts rather than overwriting an existing project's instructions.

The scope is deliberately small: Markdown, JSON, Python standard library, no hosted service or vector database. Retrieval uses explicit tags, and the checker does not certify that a written claim is true. English and Chinese templates share the same runtime.

Try the disposable demo, then tell us where the scope or retrieval misses your real workflow. Useful repros and concrete lessons matter more than a larger rulebook.

## Distribution experiments

| Experiment | Useful signal | Constraint |
| --- | --- | --- |
| Publish a tagged GitHub release with the runnable demo | Release downloads and reproducible user feedback | Do not claim unrun platform tests |
| Accurate repository topics and a readable social preview | Relevant discovery and repository visits | Avoid keyword stuffing |
| Good first issues with clear acceptance criteria | First external contribution | Do not manufacture activity |
| One relevant community demo post | Meaningful questions, trials, and issues | Check rules and disclose ownership |
| A follow-up showing a real user-reported fix | Return contributors and successful adoption | Obtain permission before sharing someone else's private context |
| Submit to a suitable curated list after meeting its criteria | Accepted, relevant listing | Read contribution rules; no bulk self-promotion PRs |

Stars are an outcome, not a guarantee. Track clones, downloads, successful starts, and contributor feedback alongside stars. Do not pay for stars, trade them, automate engagement, or use repeated unsolicited messages.

## Reference points

The presentation review considered [Spec Kit](https://github.com/github/spec-kit), [Superpowers](https://github.com/obra/superpowers), and [Context Engineering Intro](https://github.com/coleam00/context-engineering-intro). The reusable presentation patterns are a clear purpose, fast entry, real examples, and a visible contribution path. Their popularity does not prove a causal recipe for this project's growth.

GitHub documents [topics for discoverability](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics), [social previews](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview), and [community health files](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories). Reviewed 2026-10-15.

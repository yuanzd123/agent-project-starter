# Contributing

Small, reproducible improvements are welcome. Useful contributions include a regression test, a clearer setup instruction, a scoped lesson, or a translation correction. You do not need to build a new framework to help.

## Start locally

Use Python 3.10 or newer. The runtime and tests use only the standard library.

```sh
git clone https://github.com/yuanzd123/agent-project-starter.git
cd agent-project-starter
python3 tools/demo.py
python3 -m unittest discover -s tests -v
python3 tools/check_locales.py
python3 tools/check_docs.py
```

On Windows, use `python` if that is your installed Python command. No API keys or production resources are needed.

Maintainers can regenerate `assets/` with `python tools/render_assets.py`. That optional artwork tool requires Pillow and a local font; it is not a runtime or test dependency.

## Change the right source

- Runtime behavior lives in `template/`. Do not duplicate executable code in a locale.
- English prompt: `BOOTSTRAP_PROMPT.md`. Chinese prompt: `BOOTSTRAP_PROMPT.zh-CN.md`.
- Chinese template content overlays English via `locales/zh-CN/template/`.
- Lesson registry fields control status and retrieval. Keep lifecycle fields aligned across languages, and regenerate each index after changing its registry.
- `python3 tools/check_locales.py` validates both assembled templates and lifecycle parity. It cannot judge translation accuracy.

## Propose a lesson

Use the lesson issue template. Include the trigger, cause, scope, action, a reproducible validation method, evidence, and conditions that would make the advice obsolete. Redact private data. A specific dependency workaround starts as a candidate until verified for the stated version. A lesson should prevent a recurring mistake, not encode a personal preference as a universal rule.

## Send a focused pull request

Describe the problem, the resulting behavior, and how you tested it. Keep unrelated formatting and generated files out. For runtime changes, add a regression that fails without the fix. Documentation-only changes do not need artificial tests.

Report incomplete platform coverage honestly. Never weaken a check just to make CI green. Keep secrets, machine paths, private histories, and customer records out of issues and commits.

Look for [good first issues](https://github.com/yuanzd123/agent-project-starter/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22). Larger design changes benefit from a short discussion before implementation.

By contributing, you agree to the [code of conduct](CODE_OF_CONDUCT.md). Contributions are licensed under the repository's [MIT License](LICENSE).

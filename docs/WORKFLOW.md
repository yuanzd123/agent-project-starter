# Optional tiered workflow MVP

**English** · [简体中文](WORKFLOW.zh-CN.md)

The project now combines shared project memory, optional tiered model execution and independent engineering acceptance. The lightweight prompt/memory/harness entry remains usable without a model account. Python 3.10+ and the standard library are sufficient for all offline tests and demos.

Read the [complete installed-project guide](../template/docs/workflows/tiered-workflow.md) for task/config schemas, roles, budgets, the implemented JSON CLI adapter, recovery, deterministic acceptance, reports and trust boundaries. The [architecture](ARCHITECTURE.md) explains the implementation choices.

```sh
python3 tools/workflow_demo.py
python3 tools/workflow_demo.py --scenario escalation --output .local/escalation-demo
python3 tools/workflow_benchmark.py --output .local/comparison.json
python3 -m unittest discover -s tests -v
```

Output destinations must be new. The demo preserves evidence when `--output` is supplied; otherwise its temporary projects are removed. Each scenario runs real checks against a failing original and the candidate changes. The benchmark uses fixed fake outcomes and artificial prices; it is an extensible comparison interface, not evidence of real savings or model superiority.

The real CLI path is implemented and tested using local mock processes. It requires an installed bridge speaking protocol v1 plus verified model IDs, access and prices. No real provider call, credentials or paid service integration was used. Parallel implementers, provider-specific presets and learned routing remain planned.

Suggested repository description (copy only after owner review; repository metadata is not changed by this branch):

> Shared project memory, optional tiered model execution, and independent engineering checks. 共享项目记忆、可选分层执行与独立工程验收。

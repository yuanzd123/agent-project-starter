# 可选分层工作流 MVP

[English](WORKFLOW.md) · **简体中文**

项目定位为共享项目记忆、可选分层模型执行和独立工程验收。原有轻量 Prompt／memory／harness 仍可在没有模型账号时独立使用。全部离线测试和演示只需 Python 3.10+ 标准库。

[完整中文项目指南](../locales/zh-CN/template/docs/workflows/tiered-workflow.md)包含任务／配置、角色、预算、已实现 JSON CLI 适配器、恢复、真实验收、报告和安全边界。[架构说明](ARCHITECTURE.zh-CN.md)解释工程取舍。

```sh
python3 tools/workflow_demo.py
python3 tools/workflow_demo.py --scenario escalation --output .local/escalation-demo
python3 tools/workflow_benchmark.py --output .local/comparison.json
python3 -m unittest discover -s tests -v
```

输出目标必须是新路径。demo 使用 --output 时保留证据，否则自动清理临时项目。每个场景对初始失败代码和候选变更运行真实检查。对比入口采用固定 fake 结果和人为价格，仅用于可扩展实验流程，不能证明真实节省或模型优劣。

真实 CLI 路径已实现，并使用本地 mock 子进程验证。需要安装支持 v1 协议的 bridge，并核实实际 model ID、权限和价格。本次没有真实供应商调用、凭据或付费服务联调。并行实现者、供应商预设和学习型路由仍属规划。

建议仓库简介（本分支未修改 GitHub 仓库元数据）：

> Shared project memory, optional tiered model execution, and independent engineering checks. 共享项目记忆、可选分层执行与独立工程验收。

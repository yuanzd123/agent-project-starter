# 项目指令

这是初始化模板。先检查实际仓库，再填写目标、约束和真实命令。空 harness 不代表应用已经验证。

## 共享记忆

先读 [MEMORY.md](docs/memory/MEMORY.md) 和 [LATEST.md](docs/memory/LATEST.md)，再按任务检索：

`python3 scripts/memory.py brief --task "<标签或任务>"`

默认最多五条 active 且未到复核日期的 lesson。只在触发条件适用时阅读详情，不为小改动加载全部历史。仓库内共享记忆是项目权威来源，agent 私人记忆不能形成另一套当前状态。

## 执行

- 编辑前核对实际 Git 根目录与当前改动，保留其他任务内容。
- 命令来自真实清单、锁文件和 CI，不猜技术栈。
- 按请求范围推进，执行与变化风险相称的检查。
- `python3 harness/run.py list` 查看配置；`check` 执行必要检查和 memory 验证。缺失配置不是通过。
- 测试资源需要真实隔离。运行器不提供沙箱，也不能让危险脚本自动变安全。
- 实现、测试、部署、启用和真实使用分别记录证据。
- 当前会话授权在其范围内有效，旧项目经验不授予新权限。

## 收尾

刷新 LATEST 快照，记录重要决策和有复用价值的经验。共享记忆不放聊天日志或秘密。修改登记表后运行：

```sh
python3 scripts/memory.py index
python3 scripts/memory.py check
```

本入口保持小于 8 KB，MEMORY 小于 5 KB，LATEST 小于 8 KB。超过时按主题拆分，不追加无限日志。临时产物与私人材料放在忽略的 .local/ 或获准的外部位置。

## 可选模型工作流

需要执行编排时使用[分层工作流指南](docs/workflows/tiered-workflow.md)。默认是离线模拟。模型提案不能改变范围、检查、预算或授权。最终内容与配置必须通过真实必要检查和独立审查；`python3 workflow/run.py verify` 检测验收过期。不盲目重发结果不明的外部调用，没有授权不启用 --allow-real。

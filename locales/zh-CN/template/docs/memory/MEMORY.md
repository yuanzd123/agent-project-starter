# 共享记忆

这里保存经过脱敏、值得跨会话复用的工程知识，供所有 agent 使用。

1. [当前状态](LATEST.md)：事实、待办和下一步。
2. [重要决策](DECISIONS.md)：选择原因与重审条件。
3. [经验索引](LESSONS_INDEX.md)：完整导航，包含退役项。
4. [导入评审](IMPORT_REVIEW.md)：保留、改写、排除与待复核内容。
5. [项目工作流](../workflows/project-workflow.md)：命令配置与验收边界。

按任务使用 `python3 scripts/memory.py brief --task "数据 测试"`。可用标签包括 git、testing、database、cms、ui、release、security、memory，以及登记表中的中文标签。

本页只做导航，不重复保存当前部署状态。私人内容和生成产物放在忽略的 .local/ 或获准的外部位置。不安装自动上传钩子。

# 项目工作流

## 一次性配置

先检查真实项目，再在 harness/config.json 登记命令。单项目用 `path: "."`，monorepo 使用明确的仓库相对路径。不会自动执行扫描到的目录。

示例仅适用于已有 unittest 测试的 Python 项目：

```json
{
  "schema_version": 1,
  "projects": [{
    "name": "app",
    "path": ".",
    "required": ["test"],
    "checks": {
      "test": {"commands": [["{python}", "-m", "unittest", "discover", "-s", "tests"]]}
    }
  }]
}
```

使用实际项目的包管理器、运行时和 CI 约定，不给空应用编造测试。`{python}` 选用运行 harness 的解释器。不适用的阶段可以不列入 required，但应在 LATEST 说明原因。必要检查缺失时，整个计划会在执行前失败。

## 执行

```sh
python3 harness/run.py list
python3 harness/run.py check --dry-run
python3 harness/run.py test --project app
python3 harness/run.py check
python3 scripts/memory.py brief --task "数据 测试"
python3 scripts/memory.py check
```

退出 0 表示所选已配置检查通过，或明确标记的 list/dry-run 完成。退出 1 表示失败或超时，退出 2 表示缺少工具、配置错误或项目选择错误。底层失败被归一为非零退出，不保留原始数字。第一条失败后停止。

运行器不自动安装、提交、推送、部署、fetch 或读取 env 文件。但子进程继承环境，也可能读取自己的配置。执行前核对生命周期 hook、SDK 副作用和目标身份。超时终止直接子进程，脱离的 worker 需要项目自管。不在 argv 中写秘密，输出也由项目命令保证不泄露。

原生 Windows 可能需要解析后的 npm.cmd 等启动器，不给批处理参数传入未信任 shell 语法。WSL 项目在 Linux 环境使用对应工具链，不自动翻译 shell。

## 记忆生命周期

登记表维护状态、标签、摘要、复核日期和证据。正文记录适用范围、症状、原因、处理、验证和失效条件。active、candidate、deprecated、superseded 各有明确职责。替代关系必须有有效目标和原因。

稳定原则可设 review_after_days 为 null，在条件变化时复核。具体版本 workaround 激活前需要当前版本证据和有限复核周期。到期 active 不进 brief，并使 memory check 报 NEEDS_REVIEW。工具不自动删除或更新日期。

Brief 使用显式标签匹配，不是语义检索。漏检时细化标签或查完整索引。索引含退役项是为了追溯，不代表应该执行。检查只验证本地文件链接，不验证远端网页、锚点或事实正确性。

## 持续工作

按可观察结果和验收条件推进。小改动做对应检查，完整候选形成后再做必要的整体验收。刷新 LATEST，区分实现、测试、部署、启用和使用。只记录能防止未来重复错误的经验。

Worktree 中的状态可能落后。集成前核对最新相关决定，不把所有并发写入者无协调地指向同一可变快照。原始日志和私人材料留在共享记忆之外。

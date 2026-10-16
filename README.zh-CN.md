<p align="center"><img src="assets/social-preview.png" alt="Agent Project Starter：共享记忆、可靠检查、可退役的经验" width="900"></p>

# Agent Project Starter

**给 coding agent 一个清晰的起点。保留有用经验，让过时建议退出上下文。**

[English](README.md) · **简体中文**

一份可独立复制的初始化 Prompt，加上一套轻量本地工具：共享项目 memory、不会把失败当成功的 harness，以及有适用范围和复核日期的 lessons。

**直接使用：[中文 Prompt](BOOTSTRAP_PROMPT.zh-CN.md) · [English Prompt](BOOTSTRAP_PROMPT.md)。** 填写项目目标，交给 agent，让它适配你实际的代码与技术栈。

## 解决什么问题

| 常见问题 | 这里的做法 |
| --- | --- |
| 新会话忘记项目做到哪里 | 唯一记忆入口、当前状态快照、重要决策 |
| 旧 workaround 被永久沿用 | active / candidate / deprecated / superseded 生命周期 |
| 每次都加载一大堆历史 | 按任务标签检索，默认最多 5 条、4500 字符 |
| 没跑检查却宣布全绿 | 必要检查缺失或失败时非零退出 |
| 初始化覆盖已有工作 | 默认预览、完整冲突检查、不提供强制覆盖 |

工具本身不需要账号、API key、遥测、向量数据库或 Python 第三方运行依赖。你使用的 agent 和项目命令可能有各自的要求。

## 快速开始

只用 Prompt：复制 [中文初始化 Prompt](BOOTSTRAP_PROMPT.zh-CN.md) 分隔线内的内容，填写目标，在项目目录里发给 agent。无需克隆本仓库。

使用配套工具，需要 Python 3.10+：

```sh
git clone https://github.com/yuanzd123/agent-project-starter.git
cd agent-project-starter
python3 tools/demo.py
python3 tools/bootstrap.py ../my-project --lang zh-CN
python3 tools/bootstrap.py ../my-project --lang zh-CN --apply
```

Demo 在临时目录里实际演示检查缺失、命令失败、检查通过，以及过期 lesson 退出检索。不安装依赖，不访问外部服务，不修改你的项目。

![实际 demo 输出回放](assets/demo.gif)

进入新项目：

```sh
cd ../my-project
python3 scripts/memory.py brief --task "数据 测试"
python3 scripts/memory.py check
python3 harness/run.py list
```

接下来将初始化 Prompt 交给 agent，让它根据真实项目补齐 AGENTS、LATEST 和 harness/config.json，然后运行 `python3 harness/run.py check`。未配置的脚手架会明确报 NOT_CONFIGURED，不冒充业务验收成功。

Windows 可以使用已安装的 `python` 命令；WSL 项目优先在对应 Linux 环境运行。

## 已有项目如何使用

遇到不同的现有文件，初始化器在写入前停止，保留原文件。先在空的暂存目录生成，再让 agent 按 diff 合并到已有系统。完全相同的重复执行不会改写文件。已定制内容不做自动覆盖升级。

## Memory 如何保持有用

- AGENTS.md：简短规则、真实命令和读取顺序。
- MEMORY.md：导航，避免重复写状态。
- LATEST.md：当前快照、待办和证据边界。
- DECISIONS.md：重要选择及重审条件。
- lessons.json + lessons/：经验的原因、适用范围、验证方法、状态和复核日期。
- LESSONS_INDEX.md：自动生成，包含退役记录以便追溯。
- .local/：被忽略的私人材料和运行产物。

复核到期不代表经验错误。到期条目退出默认 brief，并使检查报告 NEEDS_REVIEW，由 agent 或维护者重新核实。不会自动改日期，也不会自动销毁原始证据。

随包提供 **16 条通用原则、3 类待复核经验、2 条退役记录**。英文和中文使用相同 lesson ID、生命周期与运行代码。[浏览中文 lessons](locales/zh-CN/template/docs/memory/LESSONS_INDEX.md)。

## 兼容性和边界

Codex 使用 AGENTS.md。Claude 入口仅保留一行 `@AGENTS.md` 引用，避免两份规则漂移。其他 agent 可以直接读取 Prompt 和项目入口，但不宣称已验证所有工具的原生集成。初始化后应核实实际加载的指令。

Harness 不提供操作系统级沙箱，子进程会继承环境。运行前核对项目脚本、生命周期 hook、凭据加载和真实资源身份。超时控制直接子进程，脱离进程树的 worker 需要项目自己管理。

Memory check 验证结构与复核元数据，不保证事实正确或发现全部敏感信息。Brief 使用标签匹配，不是语义检索。

## 文档与贡献

[Memory guide](docs/MEMORY_GUIDE.md) · [配置示例](docs/EXAMPLES.md) · [架构](docs/ARCHITECTURE.md) · [贡献指南](CONTRIBUTING.md) · [安全报告](SECURITY.md) · [版本记录](CHANGELOG.md)

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_locales.py
python3 tools/check_docs.py
```

欢迎贡献小而可复现的修复、翻译、配置示例，以及有证据和失效条件的 lessons。若它帮你启动或接续了真实项目，欢迎点 star，或分享一个脱敏的踩坑案例。

本项目以 [MIT](LICENSE) 开源。保留随脚手架提供的许可证声明，你自己的应用采用什么许可证仍由你决定。

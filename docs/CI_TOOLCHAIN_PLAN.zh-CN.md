# CI 改造方案：只运行已审查的预装工具链

状态：**方案草案。尚未批准任何 runner、镜像或工具链，也未启用新的 CI。**

[English specification](CI_TOOLCHAIN_PLAN.md) · [机器可读草案](ci/toolchain-contract.example.json)

## 目标与建议

保留现有 Linux、macOS、Windows × Python 3.10、3.13 共六组检查。测试时不再自动下载或安装工具链；缺失、版本不符或来源未审查，必须明确失败。

先评估 GitHub 托管的临时虚拟机与预装工具清单。每组核对具体镜像发布版本、架构、Python 补丁版本、完整发行包及其来源证据。固定 OS 标签并不等于固定镜像；镜像更新后不匹配就阻塞，不能自动扩大允许范围。

这是优先评估路线，不代表托管镜像已经满足要求。预装也不等于已审查：runner、引导 shell、Git、Python 标准库、原生扩展及动态依赖都应纳入边界。先明确并接受操作系统／平台和最初验证工具的信任基础；不能让一个未经验证的解释器运行后，再用它的自检证明自己可信。

如果托管镜像无法提供所需的源码到二进制来源证据，再考虑独立控制端管理的单任务隔离镜像。不要把长期复用、能访问私人网络或凭据的自托管机器直接连接公开 PR。自建运行环境还有维护和更新成本；此次只准备方案，不创建服务器或购买服务。[GitHub 安全指导](https://docs.github.com/en/actions/reference/security/secure-use)说明了公开仓库使用自托管 runner 的风险。

## 为什么需要改造

基线提交为 `d08cc420027c59c3982a3f1a2cc1381f96f0891d`。现有 [CI](../.github/workflows/ci.yml) 使用固定提交的 `setup-python`，但其[具体实现](https://github.com/actions/setup-python/blob/ece7cb06caefa5fff74198d8649806c4678c61a1/src/find-python.ts)仍可在缓存缺失时下载安装 Python。固定 Action 提交没有消除该行为，也没有证明下载产物来自已审查的源码。

[PR #6 的维护者要求](https://github.com/yuanzd123/agent-project-starter/pull/6#issuecomment-6260406257)适用于工具链来源。[PR #4 的审查](https://github.com/yuanzd123/agent-project-starter/pull/4#pullrequestreview-5617266432)已确认文档内容，但未批准 CI 或合并。本方案解决这一仓库基础设施问题，不修改文档示例或已有排名逻辑。

## 执行流程

上次成功 CI 的日志提供了具体起点（2026-10-18，runner 2.337.0），这些只是观察值，均未获得本方案批准：

| 环境 | 镜像发布版本 | 架构 | 实际 Python |
| --- | --- | --- | --- |
| Linux 3.10／3.13 | ubuntu-24.04，20261012.334.1 | x64 | 3.10.22／3.13.16 |
| macOS 3.10／3.13 | macos-26-arm64，20261013.0424.1 | arm64 | 3.10.11／3.13.16 |
| Windows 3.10／3.13 | windows-2025-vs2026，20261007.264.1 | x64 | 3.10.11／3.13.16 |

其中 [macOS 3.10 日志](https://github.com/yuanzd123/agent-project-starter/actions/runs/39146602309/job/117731609622)明确记录了缓存缺失、下载并安装 Python 二进制包，以及随后下载 pip 26.2.1 和 certifi 2026.10.18。因此直接删除 `setup-python` 不足以让这组环境运行。必须先找到并审查已预装所需解释器的镜像，或在测试任务之外建立已审查镜像；不能默默改成 x64 或删除 3.10。JSON 中保留了各 job 与软件清单链接。观察到的旧版本还需检查当前安全及支持状态，不能直接当作推荐版本。

1. 维护者从已审查的控制端版本启动检查，固定仓库、PR、base SHA 和 head SHA。
2. 控制端使用自身受保护的清单和验证代码，先核对运行环境，再取得固定来源的代码并确认合并候选的父提交与 tree。
3. 只用已批准的绝对工具路径执行；不从 PATH 随意选 Python，不运行安装器，不启用 Git hooks、submodules、LFS 或隐式下载助手。
4. 六组环境执行全部既有命令，记录退出码、超时、跳过情况和日志。
5. 独立可信的结果发布端核对六组真实 job 结论、候选提交和环境身份；全部通过才发布必需检查。PR 内容或输出中的“PASS”不能自行批准。
6. 合并前再核对 head 与 main；任一变化都要重新构造并验证候选。

清单、验证器和控制 workflow 必须来自已审查版本，不能由正在测试的 PR 自己修改后生效。候选任务无仓库写入、发布或生产凭据；初始权限使用 `permissions: {}`，公开源码只读取得。发布检查结果所需权限只交给独立控制端。不要在有特权的 `pull_request_target`／`workflow_run` 任务中执行外部 PR 代码。

初期可使用维护者手动触发的 `workflow_dispatch`，但它[必须先存在于默认分支](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)，不能当作新分支 workflow 的自动验证入口。手动运行成功也不会自动成为对应 PR head 的检查，需要正确绑定并发布结果。

## 保留的检查

| 平台 | Python |
| --- | --- |
| Linux | 3.10、3.13 |
| macOS | 3.10、3.13 |
| Windows | 3.10、3.13 |

每组都保留以下六条命令，用已批准的解释器替换 `python`：

```text
python -m unittest discover -s tests -v
python tools/check_locales.py
python tools/check_docs.py
python tools/demo.py
python tools/workflow_demo.py
python tools/workflow_benchmark.py
```

保留 UTF-8 设置、`fail-fast: false` 和既有超时规则；变更超时需要测量依据。保留 #5 的 Windows 字节／换行符测试。测试已有的平台跳过要如实记录；解释器缺失不能当作平台跳过。

建议新增稳定的必需结果 `Reviewed CI / acceptance`，同时配置允许的结果发布者和分支规则。只有同一候选的六组结果完整且全部成功才能满足条件。失败、取消、超时、缺失、跳过整组或未批准均阻塞合并。没有 runner 时，排队后超时也必须保持阻塞。

PR #4 最终还需针对新的合并候选重跑文档中的中英文检索。已有 Linux 本地测试不能代替其余平台的新结果。

## 工具链证据

[JSON 草案](ci/toolchain-contract.example.json)列出了六组环境、六条命令及需要记录的字段。`approved_environments` 故意为空，审批人、版本、哈希等未知信息为 null。未来验证器必须拒绝这些值，不能默认通过。

每组需要：镜像发布标识与架构、具体 Python 补丁版本、可执行文件与完整发行包摘要、标准库／原生依赖清单、源码仓库和固定修订、构建配方、依赖及源码到产物的核验记录、审查结论与有效期。哈希只能识别内容，不能单独证明产物来源。

候选执行路径优先移除 checkout/setup 等第三方 Action，改用已审查的本地源码准备流程；如果保留 Action，需审查真正执行的 bundle 及其依赖，不能仅查看 TypeScript 源码。禁用安装路径也不等于网络沙箱；若要求阻止任意候选代码联网，必须另行验证三个平台的系统隔离措施。

## 必须验证的失败场景

| 场景 | 预期行为 |
| --- | --- |
| 清单为空、未批准、过期或存在必填 null | `POLICY_UNAPPROVED`，执行候选前失败 |
| 解释器缺失 | `TOOLCHAIN_MISSING`，不下载补齐 |
| 镜像、版本、架构、原生模块或发行包摘要变化 | `TOOLCHAIN_CHANGED` |
| PR 修改清单／验证器，或伪造成功报告 | 不改变可信控制版本，也不能满足最终检查 |
| head／base 在运行时改变 | `REVISION_CHANGED`，重新验证 |
| 任一命令失败、挂起、矩阵缺项或取消 | 最终失败或继续阻塞，不能成功 |
| Git helper、路径遮蔽、恶意 shell 输入 | 执行前拒绝或禁用 |
| 复用其他提交或工具链的结果 | 汇总器拒绝 |

先在受控本地样本验证这些失败路径，再在每个已批准平台验证。不能通过先运行未经批准的解释器来探测它是否可信。

## 分阶段落地与回退

1. **本次：**提交方案与非运行配置草案到独立分支。现有 workflow 保持原样；打开 PR 也可能触发旧 CI，因此先提供分支供审阅。
2. **来源可行性：**读取公开镜像清单及源码／构建证据，补齐六组环境的缺口；明确初始信任边界后才运行探测。不满足条件的环境继续阻塞。
3. **实现：**独立实现控制端、验证器、回归样本和结果发布端，保留完整矩阵；复核全部执行入口。
4. **首次验证：**在已经批准的独立环境上运行迁移候选。没有合格环境时继续阻塞。安排受控切换，避免安装新 workflow 时触发旧下载路径；维护期间检查保持待完成／失败，不记为成功。
5. **启用：**配置必需检查与可信发布者，安装已审查的 workflow 和清单；正向六组及失败路径都验证后才启用。控制边界验证完成后再自动触发。
6. **恢复 #4：**重新读取 PR 与 main，验证候选，提交最终 Review，在提交和结果仍一致时合并。

环境更新或来源批准撤销时，阻塞对应任务并保留证据。只能回退到仍满足要求的已批准控制端／清单组合，不能恢复自动下载安装。自建 runner 还需遵守[更新和生命周期要求](https://docs.github.com/en/actions/reference/runners/self-hosted-runners)。

目前完成的是设计与验收契约。真实环境清单、精确版本和产物哈希尚未建立；控制端与验证器尚未实现；尚未执行或启用六平台 CI。PR #4 保持 Open。

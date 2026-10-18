# 可选分层模型工作流

默认工具仍无需模型账号，也不发起外部请求。`workflow/` 在现有共享记忆和显式 harness 上增加可选串行工作流。随包只有 **fake 离线模拟** provider，用于演示和测试控制器，不能衡量真实模型能力。

## 快速开始

在 starter 仓库运行：

```sh
python3 tools/workflow_demo.py
python3 tools/workflow_demo.py --scenario escalation --output .local/escalation-demo
python3 tools/workflow_demo.py --scenario repair --lang zh-CN
python3 tools/workflow_benchmark.py
```

`--output` 必须是新目录，用于保留完整演示项目、JSON 状态／报告、摘要和命令日志。四个场景为正常成功、一次同档修复、强档升级、重试耗尽。每个场景先运行真实检查并确认旧代码失败；前三个场景在模拟实现后通过同一检查。演示程序验证预期失败，因此四种行为正确时整个 demo 退出 0。

安装到自己的项目后：

1. 按[现有项目工作流](project-workflow.md)配置 [harness/config.json](../../harness/config.json) 中的真实命令。空脚手架不能通过验收。
2. 调整 [workflow/config.json](../../workflow/config.json)。每个项目的 lint、typecheck、test、build 必须在 harness 中列为 required，或在 `not_applicable` 明确写出不适用原因。
3. 调整[任务契约](../../workflow/tasks.example.json)：使用准确的相对文件路径、需求、接口和验收阶段。simulation 数据只用于离线实验。
4. 在已安装项目中运行：

```sh
python3 workflow/run.py run --tasks workflow/tasks.example.json
python3 workflow/run.py verify --tasks workflow/tasks.example.json
python3 workflow/run.py cancel --tasks workflow/tasks.example.json
```

`--root` 指定项目，配置和任务路径相对该目录。相同 ID 的 `run` 会恢复。退出 0 表示验收成功，或 verify／取消请求成功；退出 1 表示失败、阻塞、取消或验收过期；退出 2 表示配置／状态无效或不可用。也可用 Ctrl-C 或 SIGTERM 取消。取消是协作式的，不能据此认定外部付费调用没有发生。

## 控制器与任务契约

执行顺序由程序控制：

```text
任务契约 → 风险分类 → 可选架构 → 实现提案 → 限定补丁应用
→ 确定性检查 → 有限修复／升级 → 整体验证 → 独立只读审查 → 报告
```

每个任务包含 `id`、`requirements`、`risk`（low / standard / high）、`kind`（code / documentation / mechanical）、`depends_on`、`allowed_files`、`context_files`、`interfaces`、`acceptance` 和 `budget`。运行持久化 `run_id`、可选预期 `base_revision`、实际基准 revision／内容哈希、时限、尝试、状态转换、各阶段实际模型配置、调用账本、补丁和证据。预期 revision 为 null 时，接受已检查的工作目录并记录实际 revision，不假装未提交内容已经成为 Git 提交。

依赖在任何调用前做拓扑校验。缺失引用、重复 ID、循环依赖都会失败。依赖失败会阻止下游实现或最终成功。MVP 串行执行：临时检查通过后可以继续下游实现，但整合后的最终检查和独立审查完成后才算成功。

显式 high 风险不会降低；保守的关键词／路径／接口规则将权限、支付、迁移、部署等提升到 high。这只是最低风险规则，不是安全分类器，其他风险须由操作者声明。低风险任务可以跳过架构；普通代码使用 implementer 档，低风险文档和机械修改使用 fast；高风险直接 strong。架构输出是建议文本，不能新建任务、扩大文件范围或修改执行控制。强模型不逐条旁观工具调用。

状态为 `pending`、`running`、`awaiting_verification`、`repairing`、`escalating`、`success`、`failed`、`blocked`、`cancelled`；调用另有 `uncertain`。审查拒绝或越界属于失败；依赖不可用、需求不清、重试／预算耗尽属于阻塞。默认首次实现失败后，同档修复一次，再强档尝试一次，仍不通过则阻塞；次数可配置。

## 模型与资源配置

architect、implementer、reviewer 三角色映射逻辑档位。每档配置：

- `provider`、该 provider 的 `models` 白名单内的准确 `model`；
- 供应端确实支持的 `effort`，否则 null；
- `max_input_tokens`、`max_output_tokens`、`timeout_seconds`；
- `reliable_usage` 和每百万 token 价格 `price_per_million: {"input": ..., "output": ...}`，未知价格用 null。

只支持 fake 和 cli，未知 provider 类型或未登记 model 在执行前拒绝。登记是操作者对能力的声明，不是自动查询账号权限。“Opus 5.5”“Astra 6”“Sonnet”“Haiku”“6.1 Sol”等显示名称没有被硬编码成 API ID。启用前核实实际 bridge 的型号、effort、权限和现价，不预设任何组合最优。

运行级和任务级均限制 `calls`、`tokens`、`seconds`、`usd`。只有非严格金额模式允许 usd 为 null；免费 fake 可以设 0。架构、实现、失败、修复、升级和审查调用全部记账。调用前预留最大输入／输出 token 和配置价格上限，拿到实际 usage 后校正。usage 未知时保留 token／金额预留并报告 `unknown`，不记成零；价格缺失则金额未知。估算不是供应商账单，定价、额外费用、缓存及计费语义由操作者和 bridge 核实。

严格金额模式下，真实调用必须声明可靠 usage 且有有限价格上限；返回 usage 未知也会阻塞。非严格模式允许未知费用，无法计量时金额限制仅具提示性质，调用数／token／时间上限仍执行。bridge 必须遵守模型上下限，每个协议调用只发出一个计费请求，不得隐含重试或自主子调用；控制器不能约束违约 bridge 的真实账单。

控制器为所有未完成任务保留最终 reviewer 所需的调用数、token、金额，并为整体验证和审查保留时间。seconds 是包含检查、失败尝试和恢复间隔的墙钟时间；审查时间按 reviewer timeout 预留。UTF-8 请求字节数用于保守限制上下文，不等于 tokenizer 或 usage；bridge 仍须用自己的 tokenizer 执行上下限。上下文超限会阻塞，不静默截断需求或 diff。

只有**明确分类为代码错误**的检查退出码才触发修复。离线例子配置 `check_failure_categories: {"app/test": {"1": "code"}}`，因为该命令是纯断言测试。未映射的非零退出按 infrastructure 处理；类别为 code、infrastructure、dependency、ambiguity。不要把安装／网络包装命令的通用错误码标成代码错误。缺少可执行文件、超时和取消不自动升级到更贵模型，也不自动安装依赖。

## 真实 CLI 接入：协议 v1

CliAdapter 已实现实际子进程调用：绝对可执行路径和 argv，不经过 shell；stdin 接收一个 JSON 对象，stdout 返回一个 JSON 对象；校验协议／usage，处理退出、超时、取消和结果不明。这是已安装 bridge 的协议适配器，不声称任意 coding CLI 原生支持本协议。契约测试启动真实的本地 mock bridge 进程。**本次未使用真实服务、凭据或付费模型调用进行联调。**

cli provider 配置 `argv`、准确的 `models` 及可选 `env_allowlist`。以下只是结构，须替换并验证，不是可直接使用的供应商预设：

```json
{
  "kind": "cli",
  "argv": ["/absolute/path/to/your-agent-bridge", "--json-stdio"],
  "models": ["EXACT_SUPPORTED_MODEL_ID"],
  "env_allowlist": ["MY_MODEL_API_KEY"]
}
```

Windows 使用本机绝对可执行路径，优先真正的 executable／解释器，不使用 shell／批处理包装。配置只写密钥环境变量**名称**，不写值。适配器只继承基础运行变量和显式白名单变量，不主动读取 .env、用户 shell 配置或凭据。bridge 在临时工作目录运行，收到有界的文件文本／哈希、记忆 brief、需求、接口、计划、依赖状态、反馈、真实检查证据、前后 diff、验收规则及内容／配置哈希；它应返回修改提案，不直接编辑仓库。

请求包含 `protocol_version: 1`、稳定 `call_id`、`role`、`mode`（propose_changes 或 read_only）、`model`、`effort`、上下限、`task`、`files`、`changes`、`evidence` 和上述上下文。保留 call_id 供服务端对账。实现者响应示例：

```json
{
  "protocol_version": 1,
  "changes": [{"path": "app.py", "before": "SHA256_OF_REQUEST_FILE", "content": "full replacement text"}],
  "usage": {"input_tokens": 120, "output_tokens": 80}
}
```

新文件 before 为 null；既有文件必须与请求哈希一致。实现者必须返回 changes，可为空，不支持删除。架构者返回 plan 和可选 ambiguities 数组；审查者返回 `verdict: "approve" | "reject"` 与 `approved_rule_changes: ["准确路径"]`，不能提交修改。错误响应使用 `error: {"category": "infrastructure" | "dependency" | "code" | "ambiguity"}`；已知 usage 必须返回，未知用 JSON null。耗时由控制器测量，响应最多 1 MiB，stdout 不能混入进度文本。

启动后的非零退出、无效响应、超时或取消均视为结果可能不明，不盲目重发。原始 CLI stderr 不保存，以免包含凭据；返回文本包含已注入的白名单变量值时拒绝响应，检查日志会遮盖这些已知值。这不是通用秘密检测。先审查源码／上下文，使用没有生产凭据的干净环境。

仅在已明确授权外部调用后：

```sh
python3 workflow/run.py run --config workflow/config.json --tasks workflow/tasks.example.json --allow-real
```

该标记只允许本次执行已配置 CLI，不安装软件，也不证明供应端权限可用；没有自动开户、付款、发布或部署。

## 验收与安全边界

必要 lint／typecheck／test／build 和 memory 校验都是实际子进程。证据记录 argv、相对 cwd、退出码、耗时、日志路径／哈希、被测内容哈希和验收配置哈希。模型自报通过没有证明力。独立 reviewer 获取真实 diff 和证据，不能覆盖必要检查失败。独立意味着单独角色／调用和只读输出，不意味着必须是不同供应商，也不保证没有共同偏差。

补丁受准确文件白名单与前置哈希限制。绝对路径、穿越、符号链接、运行产物目录、重复路径和越界修改均拒绝。模型运行不能修改 harness、workflow、CI 控制和项目指令。识别到的测试／规则文件（含直接调用的检查脚本）必须显式列入 allow_rule_changes，并获独立 reviewer 批准；不支持删除。间接测试输入仍须人工识别并限制文件范围；更改控制规则应作为另一个审阅任务处理。

最终验收绑定整合后内容／可执行位哈希及配置，不相信模型声称的 revision。未提交补丁可能不改变 HEAD，因此同时报告 revision 和内容哈希。之后代码、测试或配置改变都会使 verify 失效。纯源码变化可以恢复后重新检查／审查，但不会重放旧补丁；配置、契约或 harness 改变必须使用新 run ID。检查的临时产物应写到 .local；检查期间其他持久内容变化会失败。.git、.local、__pycache__、.pyc 不纳入内容哈希，不能作为应用或验收源码权威。

同一工作目录只有一个 workflow writer。使用可信目录并避免并发写入。控制器和 worktree **不是操作系统沙箱**：CLI／检查可执行文件仍拥有当前用户 OS 权限。直接编辑会被前后树比较发现，但不能预先防止，也不自动回滚。POSIX 在完成／超时／取消时清理进程组；Windows 超时／取消使用 taskkill /T /F。脱离进程组的新会话 worker、以及父进程已退出后的 Windows 子进程需要外部隔离。文件校验不能抵抗恶意并发竞态或同用户任意篡改状态。对不可信工具使用容器／OS 隔离，不传生产凭据。

## 恢复、报告与故障处理

状态位于 `.local/workflow/<run_id>/state.json`，另有 report.json、summary.txt 和 check-*.log。调用预留和返回结果原子保存，三种角色的已完成响应均可复用。补丁日志在中断后接受原始哈希或已应用后的哈希，避免重复应用；完整成功运行不重复调用、记账、应用或检查。进行中的中断调用变为 uncertain，保留预留并阻塞；先与供应端核对，再明确开始任何新运行，不提供自动对账／重试 uncertain 的功能。

强制终止可能留下 `.local/workflow/lock`。确认旧进程及子进程已经停止，才删除**该锁文件**并恢复；不能删状态来掩盖未知计费。取消标记保留，核对取消结果后使用新 ID。报告存在不代表验收仍有效，应在当前 checkout 执行 verify。

常见原因：budget_exhausted（审阅额度后新运行）、deadline、context_limit（拆分任务／上下文）、dependency（修复记忆或资源）、infrastructure（检查日志）、ambiguity（澄清契约）、patch_conflict（检查手工／并发修改）、retry_exhausted、unknown_usage、uncertain_call。终止的失败／阻塞任务不自动重启。报告区分估算、预留、未知 usage 和模拟，提供基准／最终 revision 与哈希、阶段模型配置、次数、耗时、覆盖和证据。

## 对比入口与实现范围

tools/workflow_benchmark.py 在相同固定任务、初始源码和验收规则下比较全强、单一实用档、分层混合。默认是**固定离线模拟，使用人为费率和脚本结果**；测得的时间只是本地控制器／检查开销，不是服务延迟，不能据此证明模型能力、节省比例或最优组合。

后续获授权的实验可重复传入 `--report STRATEGY=path/to/report.json`。导入器拒绝不一致的任务／源码／检查指纹，以及混合真实和模拟报告。指标包括最终成功率、总费用除以最终成功任务数（计入失败、架构、修复、审查）、耗时、返工和档位升级率。未知费用保持未知；指纹不是外部审计，仍需人工核对实验规则。

已实现：串行依赖调度、有界角色、fake 和 JSON CLI 适配器、持久化记账／恢复、确定性检查、最终审查和对比报告。规划但未实现：并行实现者、供应商专用预设、自动 uncertain 对账、语义检索、学习型路由。不会保证绝对正确、最快或成本最优。

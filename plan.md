# FacetLoom 实现路线

本文件安排实现顺序、交付物与验收条件。对象、字段和运行规则以 [Design](design/00-overview.md) 为准，完整场景与验收用例见 [Demo](design/07-demo.md)。

当前仓库以设计文档和 DAG 验证示例为主，运行引擎、CLI 与 WebUI 尚属实现目标。以下阶段均待实现；文档校验通过不代表产品能力完成。

```text
1. 定义与 DAG
    ↓
2. 单 clone 执行
    ↓
3. 成果与错误 Gate
    ↓
4. 完整运行与交付
    ↓
5. WebUI 与 Refinement
```

CLI 随各阶段提供可操作的验证入口。每阶段完成验收后进入下一阶段；前期只构造后续需要的最小接口。

## 1. 定义与 DAG

**依赖：** 当前设计规范。

**交付物：** Requirement 与 current.yaml、Workflow、Facet、Scope、runner 和评估器定义的解析与校验；有序节点替换积、静态排除、旁路与传递约简、稳定 Combination ID 和 DAG 快照；必要检查累积与独立错误策略校验；CLI 定义校验与图预览。

**验收条件：**

- 相同定义生成相同 DAG；Facet 顺序、分支、汇聚和排除后的关系符合设计；补边遍历顺序不影响最终约简边集。
- 错误引用、环、悬空节点及全部节点被排除时拒绝生成运行；能查看每个 Combination 的 Gate 继承结果，runner、原生配置或评估器缺失、错配可定位；Run 完整固定执行与 AI 评估的调用配置及来源。

## 2. 单 clone 执行

**依赖：** 阶段 1 的有效定义与 DAG。

**交付物：** WorkflowRun、CombinationRun、Attempt 的文件事务及崩溃重放；preparing 阶段与 ErrorRecord；单 Worker 的 detached Worktree、预装外部 Agent 的 Podman 镜像及首个非交互 CLI Adapter；Worker / Invocation / 原生会话的独立记录；统一 Agent 证据导入协议；保留 Scope 分组的 Context Snapshot、实际初始请求留存、CheckReport、Checkpoint 和本地内容寻址 Artifact 库；单写入者的基础档案发布；CLI 启动和查看。

**验收条件：**

- 根节点从 preparing 执行到成果 waiting_gate；独立只读 Pre-Assess 先判断输入与适用性，输入不足或结果无效进入错误 Gate；不适用跳过执行但仍检查和审核。Adapter 解析原生 ExecutionResult，Runtime 结合预检与 Git Tree 判定 outcome；适用任务检查失败同次最多修复并重检 2 次，代码变化后全量重检。Post-AssessReport 与 CheckReport 均绑定最终 Tree，完整材料才冻结并发布。
- 固定代码和证据可恢复、摘要可校验；执行失败、取消和材料发布失败可查询，不丢失待发布记录。
- 无 S3、Git LFS 或共享存储时可完整执行。Artifact 先本地持久化，再发布内容引用；同 clone 按摘要去重，引用无本地路径或存储地址。回收 Worker 与 Worktree 不删除持久内容库。
- 在原生免审批模式下，Worker 仍受容器、Scope 和凭据边界约束，无法直接写 main 或人类决策。
- Adapter 完成 probe/start/continue/stop；镜像、程序、参数、配置或认证失败可定位。检查由 Runtime 独立执行，修复通过原生会话续接；缺失能力明确报错。
- Post-Assess 以新会话和只读候选容器执行，不另建 Worker；越权修改、超时或无效结果进入错误 Gate，`concerns` 作为证据交成果 Gate 审核。
- Pre-Assess、执行/修复、Post-Assess、AI Gate 与 Refinement 都可导入 `evidence_files`；传入 `evidence_refs` 仅允许引用本次请求白名单，Script Gate 只接受类型化引用。测试绝对/越界路径、符号链接、重复文件、数量和字节上限；导入任一文件失败时不发布部分结构化结果或报告。
- `wait` 仅用于 Snapshot 中固定外部引用暂时不可用；恢复后重处置原错误并用同一 Snapshot 创建新 Attempt。新增或修改 Requirement、定义或上下文时创建 replacement Run 并引用旧 Run；同一 Runtime 拥有的旧 Run 在新 Run 发布后取消，其它 clone 由旧 Run 所属 Runtime 于下次同步时取消，不能虚称即时通知。
- runner 总时限从 Pre-Assess 开始，覆盖执行、修复、检查与 Post-Assess；停止意图、30 秒默认宽限与实际退出分别持久化。

## 3. 成果与错误 Gate

**依赖：** 阶段 2 已发布的固定成果与审核材料。

**交付物：** human、ai_assisted、ai、script 的成果审核与错误处置；按 review_kind 区分的 GateReport 与 GateDecision；通过独立外部 Agent 会话执行 AI 审核，直接执行脚本审核；实际评估请求留存、人工接管与重评；CLI 审核和结果查询。

**验收条件：**

- 同一 Attempt 的各项 Gate 可并行审核，全部批准并发布后才接受成果；部分批准、AI 建议或评估故障均不能提前放行。
- 拒绝、自动评估故障、人工接管、过期请求和迟到结果按设计处理；报告更新不改变冻结的审核输入；外部程序成功退出但缺少有效结构化结论仍属故障。
- AI 成果与错误 Gate 的 `evidence_files` 经同一隔离目录导入并写入 GateReport；越权引用或导入失败产生评估故障，不生成 Decision。Script Gate 不能返回本次调用生成的任意文件路径。
- Post-Assess 的 `concerns` 不自动拒绝成果；其故障与无效结构化输出可恢复或人工接管，不覆盖原始检查报告。
- 评估器故障可对原材料重评；补测或修改成果经错误处置创建新 Attempt，全部成果 Gate 重新审核。
- 当前 clone 尚未持有所需 Artifact 时暂停审核；补齐既有引用的原内容后可重试，不改冻结字段、不把本地缺失误判为运行失败；从未形成或需要新增的证据仍须新 Attempt。
- 执行失败和成果拒绝进入 Workflow 错误 Gate；恢复动作不直接接受成果，默认整个 Run 最多自动恢复 3 次，耗尽转人类。

## 4. 完整运行与交付

**依赖：** 阶段 3 的分项决策与成果接受机制。

**交付物：** DAG 并行调度、稳定排序、逐步基于真实共同祖先的多前驱汇聚、冲突清单、Scope 校验、受控重试与后继失效传播；Runtime 重启、原生会话能力检查与未知调用对账；archive / advance / delivery 发布分类及取消竞争；main 档案并发发布和 clone 协作；Artifact 交换包的闭合依赖导出、校验与原子导入；人工 purge 的保护检查、预览、确认及本地回执；可恢复的最终候选、IntegrationReport、绑定候选的交付确认与回执；CLI 取消、重试、恢复、交付与 Artifact 管理。

**验收条件：**

- 通过 CLI 跑通登录限制 Demo：分支并行、汇聚等待全部前驱、冲突处理、审核和最终交付。
- 事务提交前后崩溃、外部调用未知、推送失败和重复操作不丢记录、不重复扣减恢复额度、不重复接受或交付；不同 clone 的档案互不覆盖。仅同步 Git 时明确标记缺失 Artifact，经现有渠道传递并导入独立交换包后，可从其中 Git bundle 恢复代码，不接管活动运行。
- 导出缺少依赖即失败；导入校验来源 Git 记录、完整依赖、路径、大小和摘要，损坏、重复成员、链接、缺少或多余文件不能产生有效的部分导入结果；重复导入及中断恢复幂等。
- purge 保护活动、待审核、待交付、待发布、恢复和其它有效记录的传递依赖；预览过期重新确认。人工删除仅历史依赖的内容先记本地回执，删除失败可重放；不改变 Git 冻结记录或其它 clone，重新导入可恢复内容，不承诺全局销毁。
- 需求取代与上游修复正确停止或失效相关执行；过期成果不能交付，仅档案变化不使运行输入失效；旧需求仍可归档取消及历史证据。
- Replacement Run 显式关联被替代 Run；新运行档案未发布前旧 Run 保持有效，同一 Runtime 拥有的旧 Run 在发布后取消，其它 clone 由旧 Run 所属 Runtime 在下次同步时取消；任何 clone 在发布后都不能再推进旧 Run，记录不被删除。
- 重启不重置总 deadline；PID 复用、容器查询失败、停止未确认和原生恢复不支持时，不重复启动或误判已退出。
- 取消撤销未发送的 advance，推送在途或确认丢失时先对账；历史终态保留，迟到批准不能解锁后继。
- 最终检查通过并经绑定候选的人类确认后交付 main，保留最新档案；同一 Run 最多一次成功交付，无代码变化只提交回执，未形成候选不能伪造报告字段。

## 5. WebUI 与 Refinement

**依赖：** 阶段 4 的完整运行能力与真实运行档案。

**交付物：** Requirement、Workflow/DAG 预览、运行状态、Diff、证据、成果审核、错误处置与双重预算、交付页面及 runner、调用和停止对账详情；Artifact 可用性、交换包与本地清理页面；运行精炼的独立外部 Agent 会话、记录筛选、建议、采纳、验证与清理；精炼 CLI。界面与 CLI 使用相同服务和校验规则。

**验收条件：**

- 通过界面完成 Demo，明确区分本地实时状态、已发布档案、运行完成和交付完成。
- 调用详情能查看证据文件路径、导入状态、摘要和持久引用；整批导入失败时显示原因且无可引用的部分报告。错误页面只在固定引用暂不可读时允许 wait，并呈现同 Snapshot 重试与 replacement Run 两种恢复结果。
- 至少一项真实运行经验转化为经验证的改进，并在同一提交中清理对应记录。
- 部分采纳、验证失败、来源变化、会话中断和回退均可处理；保留未解决问题及有效引用，不误删活动、待审核或待交付证据。
- Artifact 页面区分本地可用、尚未导入、已在本地清理和缺失/损坏；导入既有内容与新增证据分开。Refinement 不自动 purge，Git 回退不显示为已恢复被删除的 Artifact。

Codex、Claude Code、OpenCode、Pi Agent 是 Adapter 接入目标；阶段 2 先完成一种，其他按同一协议逐项验证，不要求自建模型或工具循环。

## 后续探索

当前路线完成后，再评估独立契约版本管理、精确影响分析与选择性重验证、自适应 Facet、Agent 能力匹配、历史回放和跨项目经验。S3 或 LFS 等可选 Artifact 后端、自动副本发现、P2P 传输、多用户精细权限及活动运行跨 clone 接管待实际需求明确后设计，不作为当前阶段的验收要求。

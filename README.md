# FacetLoom · 维织

**Multi-Facet AI Engineering Studio**

FacetLoom 围绕一个冻结的 Requirement，用多个 Facet 从不同角度拆解和对齐需求，再通过 Combination DAG、并行执行、Git Checkpoint 和可配置 Gate 形成可审核的交付。

> 需求有去向，任务有边界，产物有证据。

当前核心是单次 Requirement 的对齐、执行、审核与交付。跨多个 Requirement、Commit 和 Release 的架构治理、漂移检测、质量趋势等属于长期发展方向，不是当前实现范围。运行所需的上下文引用、检查、Verification、Artifact 与 Gate 证据属于单次交付闭环。

## 核心模型

需求默认由 AI 辅助起草，可随时切换纯手动模式；当前 clone 保存默认选择，每个需求可覆盖。起草独立选择外部 Agent runner，AI 修改本地草稿，人类审阅后冻结并启动工作流。

Workflow 按 Facet 声明顺序应用节点替换积，每个 Facet 用 DAG 组织上下文 Node。运算从外到内且不满足交换律，因此 Facet 顺序会定义 Combination DAG 的拓扑。`exclude` 在完整 DAG 生成后按 Combination 的 Facet→Node 来源映射匹配；删除命中节点后补齐旁路边，再对整个结果做传递约简，保留相同依赖顺序并去除冗余边。Combination 是执行单元，互不依赖的分支可并行，汇聚节点等待全部前驱。

```text
Feature: start → Login ────────→ end
         start → Notification → end

Layer:   start → Domain ─┬→ Application ─┐
                         └→ Data ────────┴→ Presentation → end
```

每次运行用 `source_commit` 固定定义、资料与代码基线，用 `requirement_ref` 固定本地冻结的需求。一个需求使用独立 UUID，最终对应 main 上一个 squash 采纳提交。Git 只保留 main 分支，Worker 在 detached Worktree 和 Rootless Podman 环境中执行。镜像预装外部 Agent 及项目环境；runner 固定镜像、原生参数和配置。FacetLoom 调用 Codex、Claude Code、OpenCode、Pi Agent 等程序，不实现 Agent 引擎；原生免审批模式不改变 Scope 校验、必要检查和 Gate。

```text
main：Requirement + Workflow + Facets + 正式代码 + 精简运行档案
    ↓ source_commit
本地 Runtime → Combination DAG → 并行 Worker / Worktree
    ↓
必要检查与预算内修复 → Checkpoint → 各 Node 的 Gate 全部批准 → 汇聚
    ↓
最终集成检查与人类确认 → 需求、代码、精简档案和回执一次 squash 到 main
    ↓
Refinement → 人类筛选记录 → Agent 建议 → 采纳并验证
    ↓
改进与已处理记录清理，同 Commit 提交 main
```

## 主要对象

| 对象 | 含义 |
| --- | --- |
| Requirement | UUID 标识的独立需求；首次运行前冻结，内容变化创建新需求 |
| Workflow / Facet（Source Facet）/ Node（Facet Node） | 组合图规则、上下文维度和维度内节点 |
| Combination（Combination Node） | 节点替换积生成、带 Facet 来源映射的业务执行单元 |
| WorkflowRun | 固定输入与 DAG 的一次运行 |
| CombinationRun / Attempt | 一个节点的运行状态及一次执行、重试或评估 |
| Runner | Git 管理的外部 Agent 调用配置 |
| Worker / Invocation | 一个 Attempt 的隔离执行生命周期及一次外部调用 |
| ErrorRecord | 准备、执行失败或成果拒绝的不可变错误材料 |
| CheckReport | Runtime 的必要检查轮次、被检查 Tree 与真实结果 |
| GateReport / GateDecision | 成果审核及错误处置的报告与决定，均支持四种模式 |
| Refinement | 人机筛选运行记录、落实改进并清理已处理记录的过程 |

## 存储与协作

```text
.facetloom/
├── requirements/ workflows/ facets/ references/ runners/ evaluators/  # main 上的正式定义
├── runs/<run-id>/                                 # main 上的精简档案
└── .runtime/                                     # 本地状态与持久 Artifact 库，不进入 Git
```

每个协作者在自己的 clone 创建不同 Run。执行与 Gate 由本地文件事务保存并生效；只有最终采纳时才把需求、代码和必要的精简档案一次提交 main。失败、取消或放弃的记录留在本地，可显式导出。SQLite 仅可选索引。大型证据、实际调用输入和完整对话保存在本地 Artifact 库；Git 外的代码快照用自包含 Git bundle 保留。记录覆盖 FacetLoom 提供的输入与可观测事件，不承诺外部 Agent 的隐藏推理或内部模型请求。

所有项目统一使用本地事务推进执行与 Gate，以一个提交进入 main 完成需求采纳；精炼另作维护提交。无需 remote 即可完成全部操作。remote 仅用于用户按需同步更新；推送失败不撤销本地结果。其它 clone 的修改在同步到本地 main 后才影响运行，冲突需明确协调，系统不承诺全局即时一致。

Git 同步已采纳档案，内容按需传递：未采纳记录可冻结为本地快照，所选记录及依赖导出为独立 Artifact 交换包，协作者通过现有渠道传递并校验导入。引用采用内容哈希，不是下载地址；其它 clone 未导入时仍可看摘要，需要材料的审核或恢复则暂停。默认不依赖 S3、Git LFS 或中心存储服务。

审核定义统一进入 Git。Workflow 与 Node 的必要检查累积，同一 Attempt 默认最多修复并重检 2 次；完成后冻结成果输入。执行失败或成果拒绝交给独立错误 Gate，决定重试、修复上游、等待或停止；默认人工，每个 Run 最多自动恢复 3 次。恢复获准不代表成果被接受，补测或修改冻结成果需要新 Attempt。

只改变运行档案不会使运行输入失效。交付前对比 source_commit 与最新 main，排除 `.facetloom/runs/` 后有代码或定义变化则创建新 Run；交付提交保留最新档案。确认绑定具体候选与最终报告，同一需求最多一次成功采纳；无代码变化也须检查和确认，同一提交保存需求与 no_change 结论，回执不自引 Commit OID。冻结后需求变化创建新 UUID；已采纳成果可 Git revert，历史保留且不重开原需求。需求列表按采纳顺序展示，序号仅用于阅读。

Refinement 的界面入口为「运行精炼」，CLI 为 `facetloom refine`。采纳项验证成功后才清理对应记录；暂留问题、活动运行、待 Gate 和待交付证据继续保留。原记录通过 Git 历史追溯，清理目标是当前目录与 Agent 上下文，不重写历史。

Artifact 默认保留，释放空间须另行人工 purge，先检查完整依赖并确认影响。它只删除当前 clone 的内容并留下本地回执；不会删除协作者、交换包或备份中的副本。Git 回退可恢复记录，无法恢复另行删除的 Artifact。

## 当前验证范围

- 两个包含分支与汇聚的 Facet，生成并校验 Combination DAG。
- 单 clone Runtime 的并行、Checkpoint、本地恢复及不同 clone 的档案协作。
- 本地 Artifact 持久化、独立交换包导出/导入、缺失材料提示与人工清理保护。
- 四种 Gate 模式、Node 成果全部批准规则与 Workflow 错误处置；最终集成检查及人类交付确认；Worker 不持有 main 推送凭据。
- 最小 WebUI / CLI：DAG、Diff、日志、审核、运行精炼。

首个场景为“登录失败五次后暂时限制登录，并显示剩余等待时间”。当前仓库以设计文档为主，CLI、WebUI 与上述协议是实现目标；安装和部署方式在实现阶段确定。

## 文档

- [Design](design/00-overview.md)：按 00–07 阅读的实现规范。
- [Plan](plan.md)：实现阶段、依赖与验收条件。
- [Idea](idea.md)：产品目标、架构动机和长期发展方向，具体协议以 Design 为准。

## 命名约定

| 项目 | 名称 |
| --- | --- |
| 项目 | FacetLoom |
| 中文名称 | 维织 |
| 仓库 / CLI | facetloom |
| 项目配置目录 | .facetloom/ |

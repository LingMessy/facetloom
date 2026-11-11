# 多切面组合执行的 AI 软件工程系统

**产品构想与架构动机**

**文档定位：产品目标与后续构想；当前对象和协议以 [Design](design/00-overview.md) 为准。**

> **一句话定义**：一个通过多个 Source Facet 及其内部 Node DAG 从多个维度拆解软件，在派生的 Combination Node DAG 中执行 AI 开发，并通过可配置 Gate 持续进行需求对齐的 Git 原生自动化软件工程系统。

## 0. 阅读指引

Workflow 与 Facet 表达上下文和依赖，Combination 承担执行，Runtime 负责调度。每次 Run 用 source_commit 固定执行定义与代码基线，用 requirement_ref 固定独立 UUID 的需求，Worker 在隔离 detached Worktree 中并行执行。

一个需求最终对应 main 上一次 squash 采纳提交，同时保存需求、代码和精简运行档案。执行和 Gate 在本地事务落地后生效，失败或放弃不提交 main。本地状态恢复活动运行，Git 共享已发布档案与证据引用，大型内容经独立 Artifact 交换包按需传递。Refinement 通过人机交互筛选记录、提出改进，落实并验证后清理已处理记录。

具体文件、状态机、交付与精炼协议见 design；本文件解释产品动机和可能的扩展。Source Facet、Facet Node、Combination Node 在设计中简称 Facet、Node、Combination；本文的 Combination Facet 指派生的 Combination DAG，不另设对象或文件。

## 1. 出发点与目标

### 1.1 核心判断

AI 的代码生成能力不断提高，但快速生成 Demo 并不等于长期可维护、安全稳健的软件。开发过程还必须将人的真实目标与 AI 的设计和实现反复对齐。即使 AI 能自行发现问题和提出下级需求，系统仍需要清晰的人类目标、授权边界和决策依据。

### 1.2 当前目标与长期方向

1. **更少的人工成本**：Gate 支持人类、AI 辅助、AI 与脚本决策；人类确认需求、正式发布与最终交付。
2. **更快的开发速度**：多个 Requirement 并行；在组合中先 Assess，避免不必要的实际修改。
3. **多角度需求对齐**：一个 Requirement 通过 Feature、Layer、Verification 等 Facet 拆解；Combination DAG 组织不同角度的工作依赖，并行推进且保留清晰边界。
4. **安全稳健**：容器隔离、自动测试、可追踪 Gate 决策、Git 检查点与安全交付。

**研发理念**：减少人类对代码实现细节的持续监督，增强人类对目标、关键设计与授权范围的控制。

长期可维护的软件工程是产品愿景，但当前核心只覆盖单次 Requirement 的多 Facet 对齐与交付。跨需求、Commit 和 Release 的治理能力留待后续阶段：逐步建立长期追踪与持续检查，再将治理发现转成经人类确认的新 Requirement，交回现有 Workflow 执行。它不扩展成额外的开发 Facet，也不属于当前实现验收范围；上下文引用、检查、Verification、Artifact 和 Gate 在当前阶段只承担单次运行所需的定义、检查与证据闭环。

## 2. 核心概念：理解系统所需的主要对象

| 概念 | 定义 | 是否执行开发任务 |
|---|---|---|
| **Requirement（需求）** | UUID 标识的一次独立需求；本地冻结，最终与成果一起纳入 main | 否，驱动执行 |
| **Workflow（工作流）** | 定义 Source Facet、Facet Node DAG、Combination Facet 及其生成规则的版本化结构 | 由 Runtime 运行 |
| **Source Facet（源切面）** | 用户定义的一个拆分维度，内部包含 Facet Node DAG，例如 Feature、Layer、Quality、Verification | 否 |
| **Facet Node（切面节点）** | Source Facet 中的上下文节点，提供范围、规则、输入和约束 | **否，绝不单独执行** |
| **Combination Facet（组合切面）** | 由多个 Source Facet 按 Workflow 条件过滤后派生的执行切面；在 Workflow 版本内固定 | 否，承载执行图 |
| **Combination Node（组合节点）** | 从每个 Source Facet 选择一个 Facet Node 形成的节点，属于 Combination Node DAG | **是，唯一的业务执行单元** |
| **Combination Worker（组合执行器）** | Runtime 为一个 Attempt 管理的隔离容器、Worktree 与调用生命周期 | 调用外部 Agent 执行 Combination Node |
| **Gate（决策关卡）** | 针对组合执行成果的需求对齐、验收或授权 | 作为组合执行的一部分 |

**Artifact** 不是独立版本化的核心实体，而是组合执行过程中产生和传递的文件、规范、代码、报告等中间成果，正式代码和精简证据索引由 Git 管理，大型内容保存在每个 clone 的本地持久内容库。

### 2.1 特别重要的边界

- Facet Node 提供任务上下文和 Gate 声明，不拥有独立 Agent 执行或 Artifact 生产；审核发生在组合后的 Attempt 上。
- 每个 Source Facet 都有自己的 Node DAG；Source Facet 之间不建立 DAG 边。
- Combination Facet 是由多个 Source Facet 派生出的执行 Facet，不引入新的业务维度，也不由用户直接维护节点；第一版以 Workflow 版本为生成和复用边界。
- Workflow 在定义阶段根据已配置条件过滤候选组合并生成 Combination Facet；Requirement 运行时不重新生成另一张结构不同的 Combination Facet。
- Combination Node 是从每个 Source Facet 选择一个 Facet Node 后形成的组合执行上下文，也是 Combination Node DAG 中的真实业务节点。
- Requirement 启动时绑定一个不可变的 Workflow 版本；Workflow 修改产生新版本，运行中的 Requirement 不切换版本。
- 不设置独立的 Requirement Gate；需求级验收或验证由用户在显式的 Verification Source Facet 中创建验证用途的 Facet Node，生成 Combination Node 后按普通执行和 Gate 规则处理。
- 每个 Combination Node 在完整上下文中由 Combination Worker 运行 Assess → Execution（必要时）→ Artifact/Git Checkpoint → Gate。
- Agent 可以提出需求、上下文或 DAG 修改建议，但不能未经授权直接修改已激活的 Workflow 或 Combination Facet。
- 独立的 AI Scheduler 不负责预先分析并分配全部需求。Workflow Runtime 只负责读取 Combination Node DAG、启动和监督 Worker、处理依赖、并发、重试与恢复。

## 3. Facet 与 Combination Facet：源图与派生执行图

### 3.1 Source Facet 的 Node DAG

每个 Source Facet 都是一个独立的 DAG。`start` 和 `end` 是控制边界，不是可执行的 Facet Node。

```text
Feature Facet:
start → Login → end
start → Notification → end

Layer Facet:
start → Domain → Application → Presentation → end
```

Facet 内的边表达依赖顺序；Node 自身不执行或产生成果。Workflow 按声明顺序应用节点替换积，将这些依赖展开为 Combination 之间的依赖。Source Facet 之间不直接连边，成果由运行时按最终组合 DAG 汇聚。

### 3.2 Combination Facet 与 Combination Node DAG

Workflow 固定版本中的多个 Source Facet 派生出一个 Combination Facet。Combination Facet 不增加新的业务维度，而是承载由 Combination Node 构成的执行图。

从每个 Source Facet 选择一个真实 Facet Node，形成一个 Combination Node：

```text
Login × Domain
Login × Application
Login × Presentation
```

Workflow 按声明顺序从外到内应用节点替换积。`G ▷ H` 将 G 的每个普通节点替换为一份 H 的实际子图；对 G 的依赖 `u → v`，连接 u 副本的全部出口与 v 副本的全部入口：

```text
u 内的 H 子图：全部出口 → v 内的 H 子图：全部入口
```

因此 `feature ▷ layer` 会形成以下分支，省略最终 end：

```text
Combination Facet
└── Combination Node DAG

start
  ├─ Login × Domain
  │      ↓
  │  Login × Application
  │      ↓
  │  Login × Presentation
  │
  └─ Notification × Domain
         ↓
     Notification × Application
         ↓
     Notification × Presentation
```

`Login × Domain` 与 `Notification × Domain` 之间没有依赖，因此可以并行。执行顺序由合并后的 Combination Node DAG 决定；字典序不再是执行规则，最多只能作为同一批就绪节点的稳定展示或调度顺序。

替换积不满足交换律，调换 Facet 顺序可能改变并行与汇聚关系。内层只保留实际节点，最外层保留 start/end；完整算法见 [Workflow](design/01-workflow.md#组合-dag-的生成规则)，顺序影响见 [验证位置对比](design/01-workflow.md#facet-顺序与验证位置)。

当多个前置路径在同一个 Combination Node 汇聚时，Runtime 通过 Git Manager 按固定算法形成输入和冲突清单。当前 Attempt 的 Agent 在有效 Scope 内解决代码集成冲突；越界冲突或前驱行为不符合需求时交错误 Gate 处置，不静默修改上游责任。

Combination Facet 在 Workflow 版本内固定。Requirement 启动时创建该 Combination Facet 的运行实例，记录上下文快照、执行状态和结果，但不重新定义另一张结构不同的 DAG。Workflow 修改后产生新版本，已有运行继续使用原版本。

### 3.3 两个典型 Source Facet

**Feature Facet**（功能维度）可以包括：登录、通知、个人中心。  
**Layer Facet**（架构维度）可以包括：Presentation、Application、Domain、Data。

`Login × Domain` 是一个 Combination Node，表示：**在登录 Feature 的业务范围中，按照 Domain 层职责和约束，判断、设计和实现本次相关修改。**

`Login × Presentation` 则表示：同一个登录 Feature，在 Presentation 层的具体设计与实现。

也可以在后续增加 Quality Facet（Security、Accessibility、Performance 等），而不需要发明新的底层 Node 类型。

**Verification Source Facet** 是用户定义的验证维度，按普通 Node 与组合规则执行。验证范围和等待关系取决于 Facet 顺序、拓扑及上下文，名称不产生特殊调度语义；最终集成检查与人类交付确认仍负责整体验收。

### 3.4 组合上下文的构成

一个组合运行时读取：

- 原始 Requirement 与已确认的需求约束；
- Workflow 的全局规则；
- 当前 Combination Node 选中的各 Source Facet Node 上下文（例如 Login + Domain）；
- 当前 Attempt 的输入代码、已接受前驱成果及 Artifact 引用；
- 适用的权限、环境与 Gate 策略。

**原则**：上下文是层层绑定的；不同 Node 的约束冲突时不能默默以后者覆盖前者，应暂停并进入评估或 Gate。

### 3.5 定义阶段条件过滤

Workflow 按声明顺序对 Facet DAG 应用节点替换积，先生成完整 Combination DAG，再按节点来源映射应用静态排除。删除中间节点后补齐旁路边，再对整个结果做传递约简，保留相同依赖顺序并去除冗余边。固定后的 DAG 随 WorkflowRun 保存；Requirement 运行时的 Pre-Assess 不改变图结构。

例如：

- `Login × Presentation × Accessibility`：通常适用；
- `Login × Domain × Accessibility`：一般不需要专门的 UI 无障碍检查；
- 认证、授权及敏感数据相关组合：需考虑 Security 检查。

静态 exclude 仅按 Facet→Node 来源映射匹配，格式与校验见 [排除规则](design/01-workflow.md#排除规则)。上例是配置时的判断依据，不是运行时 AI 自动删节点的规则。运行时是否适用由 Pre-Assess 留存理由与证据；无法判断进入错误 Gate，不默认跳过验证。

### 3.6 Workflow 与 DAG 的激活不变量

Workflow 版本只有在以下条件都满足时才能激活：

- 每个 Source Facet 的 Node DAG 和生成的 Combination Node DAG 都无环；
- `start` / `end` 只表示控制边界，不启动 Combination Worker；
- 每个被激活的业务节点从 `start` 可达，并且能够沿依赖路径到达 `end`；
- 所有依赖边都指向同一张已生成且已校验的 Combination Node DAG 中的节点。

条件过滤或 Agent 建议导致的非法图不能直接进入运行；必须先由 Workflow 校验拒绝或由用户修订后重新生成版本。

## 4. Combination Node 与 Combination Worker：真正的执行单元

Combination Node 是静态的业务执行节点；Combination Worker 承载一次 Attempt 的容器、Worktree 与调用生命周期。每个 Attempt 最多有一个 Worker，由 Runtime 经 Adapter 调用容器内的外部 Agent；Runtime 独立执行检查，Git Manager 保存代码快照。FacetLoom 不实现 Agent 的模型推理、工具循环或上下文压缩。

每个 Combination Worker 遵循统一的执行协议：

```text
Combination Node 输入上下文
    ↓
Pre-Assess：是否相关、是否需要修改、输入是否充分
    ↓
Execution（可跳过）：外部 Agent 原生执行
    ↓
Artifact：输出文件、规范、代码、报告
    ↓
Git Stage → Git Commit（有实际变更时）
    ↓
Post-Assess：完整性、额外影响、上游问题
    ↓
Gate：各 Node 的审核项按配置决策，全部批准
    ↓
Approved → DAG 中的后继节点可能就绪；Rejected → 修复相关 Combination Node
```

Runtime 根据 Combination Node DAG 找到所有前置节点已经满足依赖的节点，并在并发限制内启动多个 Combination Worker。没有路径关系的 Combination Node 可以并行；有多个前置节点的节点必须等待所有前置节点完成或达到可继续状态。

建议的运行记录层次为：

```text
Combination Node       // Workflow 版本中的静态节点
CombinationRun        // 某次 Requirement 运行中的节点记录
Attempt               // 一次实际尝试或重试
Combination Worker     // 承载 Attempt 的容器、Worktree 与调用
```

### 4.1 Pre-Assess

在当前 Combination Node 的职责范围内判断：

- 是否与本需求有关；
- 需不需要修改现有工程文件；
- 缺少哪些输入、契约或上游设计；
- 是否触及更高风险、需要额外审核。

若 Pre-Assess 判定不需要修改，可以跳过代码修改与空 Commit；仍按固定图完成必要验证和各项 Gate，以 no_change 或有理由的 not_applicable 记录结果。

### 4.2 Execution 与 Artifact

Combination Worker 中的 Agent 在隔离环境中操作**当前 Attempt 的 Worktree**。同一 Requirement 内并行的 Attempt 使用不同 Worktree。Artifact 可以是 Markdown 规范、接口 Schema、源码、测试报告、原型等；组合间通过固定代码输入与证据引用衔接。

### 4.3 Post-Assess 与 Gate

Post-Assess 检查是否遗漏相关变更、是否引入其他模块影响。Gate 决定是否接受该组合成果、继续执行、返回上游组合或请求人工。

**Facet Node 可声明 Gate**，未声明字段继承 Workflow 默认；每个选中 Node 贡献一项审核，评估 Combination 的当前 Attempt，全部批准才接受成果。

## 5. Gate：对齐与验证

Gate 持续检查组合成果是否符合人类需求、架构和功能行为。Gate 有 human、ai_assisted、ai、script 四种模式，分别由人类、人类、AI、程序决策。成果项可以并行；执行失败或成果拒绝由 Workflow 错误 Gate 决定重试、上游修复、等待或停止，评估器自身故障交给人类。最终交付仍由人类确认。

每个组合读取完整 Requirement，各 Gate 从所选 Node 的角度审核当前职责内的成果。局部批准不表示整个需求已完成，后续节点负责的工作也不要求在当前节点提前实现；当前约束与必要检查始终有效。示例见 [需求对齐表](design/07-demo.md#同一需求如何从不同角度对齐)。

Requirement 不拥有独立 Gate；Verification Facet 表达节点级验证，最终集成检查验证整体结果。执行与必要检查完成后固定审核输入；Gate 报告属于审核输出，不回写执行证据。补测或修改成果需要新 Attempt，不能复用旧批准。审核定义统一进入 Git，执行与评估的实际初始请求通过持久 Artifact 留存。

成果结论为 Approved、Rejected、Escalated、Blocked；错误处置单独输出动作，不把允许重试视为接受成果。修复后相关后继重新评估，决定和结果通过本地事务生效，采纳时才归档 main。

## 6. 上游回退：逻辑回退，而不是默认重写 Git

例如：

```text
Login × Domain        （C1）
Login × Application   （C2）
Login × Presentation  （C3）← Gate 发现领域设计错误
             │
             └── 返回 C1 修复，创建新的 Git Commit
                          ↓
                 C2、C3 重新 Assess / 验证
```

**默认策略**：错误 Gate 决定重试当前节点或修复祖先，Runtime 在决定本地落地后安排新 Attempt；修复目标及全部后继失效，按依赖重新执行，历史结果保留为证据。

**特殊策略**：如果设计方向需要整体放弃，可从旧检查点创建新的隔离 Worktree，保留原历史作参考；不默认执行破坏性的 `git reset --hard`。

**恢复边界**：每个 Run 默认最多自动恢复 3 次，耗尽后由人类决定；同一 Attempt 内默认最多修复并全量重检 2 次，两者独立计数。精确影响分析和选择性重验证留待后续探索。

## 7. Git：正式内容与精简运行档案

```text
main：正式定义 + 已接受代码 + .facetloom/runs/<run-id>/
    ↓ source_commit
    ├── detached Worktree A → 本地 Checkpoint
    └── detached Worktree B → 本地 Checkpoint
                                  ↓
                          汇聚与分项 Gate 审核
                                  ↓
                        最终检查与交付 main
```

每个 clone 的 Runtime 独立运行，各 Run ID 隔离档案路径。并行 Worker 用独立 Worktree，不创建命名执行分支。代码快照需要长期或跨 clone 复核时导出 Git bundle 保存到本地 Artifact 库；YAML 中的 Commit ID 不保证对象被保留。跨 clone 共享时导出包含完整依赖的独立 Artifact 交换包，通过现有渠道传递并校验导入；Git bundle 是包内的一种内容。默认不依赖 S3、LFS 或中心存储服务。

main 上仅运行档案变化不使输入失效；交付比较排除 runs 目录后的正式内容，在最新 main 上保留档案并应用成果。Agent 不直接写 main，Git Manager 根据人类确认更新正式代码。

### Refinement（精炼）

```text
已结束运行的记录 → 人机筛选事实与问题 → Agent 建议与 Diff
                                           ↓
                                  人类采纳、暂留或丢弃
                                           ↓
                              应用并验证 → 改进与清理提交
```

只清理已解决或被人类明确丢弃的记录，保留未处理问题及仍被有效引用的证据。验证失败不删除。依据写进改进 Commit，引用删除前的 Git 文件；历史继续可追溯。目标是减少当前目录和 Agent 上下文，不改写 Git 历史以压缩仓库。

完整对话和大日志的持久内容保存在本地 Artifact 库，临时输出不作为唯一证据，不自建第二套 Artifact 版本系统。内容默认保留，人工 purge 另行检查依赖，只删除当前 clone 的副本；Git 历史与协作者副本不受影响，回退 Git 不会恢复已删除文件。Worker 容器不获得 main 凭据、整个 Artifact 库、可写共享 Git 元数据或 Podman 管理 Socket；Worktree 之外仍需执行限制与挂载隔离。

## 8. Podman：隔离 Agent 与开发环境

建议默认使用 **Rootless Podman**，按 Attempt 提供独立容器运行环境，镜像预装外部 Agent 与项目依赖：

- runner 固定镜像 digest、原生参数和配置；可关闭外部 Agent 的内部审批与沙箱，Podman 隔离、Scope 校验、必要检查和 Gate 仍由 FacetLoom 执行。
- 不同 Attempt 使用独立容器、Worktree 与原生会话；同一 Worker 可在检查预算内续接 Agent 多次修复。回收前确认退出并持久化证据。
- 一次性测试或高敏感检查可用 `--rm` 临时容器。
- 并行写入的 Combination Worker 使用独立 Worktree + 容器。
- 代码在 Git Worktree，持久 Artifact 在本地内容库，工具链在镜像，依赖缓存可在受控 Volume；容器内部临时状态不应成为唯一结果来源。
- Git Stage/Commit/Merge 由宿主机可信 Git Manager 负责，不让 Agent 拥有跨分支修改权限。
- Android 模拟器、设备/KVM 等特殊测试任务可使用单独受控的执行环境，不给普通编码 Agent 默认特权容器。

## 9. WebUI、无头 Runtime 与运行状态

### 9.1 产品形态

采用**WebUI + 后台 Runtime**，本地或 Linux 无头服务器均可运行。关闭浏览器或 SSH 连接后，Workflow 仍可继续执行。

- **WebUI**：Source Facet / Facet Node 编辑器、Combination Facet 与 Combination Node DAG 预览、Git Diff、日志、Gate 分项审核与人工接管、运行精炼、运行监控。
- **Workflow Runtime**：读取 Combination Node DAG，判断就绪节点，启动和监督 Combination Worker，处理依赖、有限并行、失败恢复与 Gate 流转，**不另设 AI 智能调度器**。
- **Combination Worker / Agent Adapter**：由 Runtime 启动，调用预装的 Codex、Claude Code、OpenCode、Pi Agent 等外部程序，负责一次 Attempt 的实际生命周期；Adapter 仅适配原生协议。
- **Git Manager / Podman Manager**：提供经过权限控制的宿主机操作。

技术倾向：Rust + Axum；前端 React + React Flow。这些是建议选型，不是核心领域语义。

### 9.2 状态存储

Runtime 持久化本地就绪队列、活动 Attempt、Worker/容器引用、重试与恢复状态。Git 保存已采纳需求、Workflow 定义和精简档案；需求、代码和交付记录在同一 Commit；大体积日志保存在 Git 外，持久证据使用不可变引用。SQLite 可用于本地缓存与索引；Git 只恢复已发布档案，不保证恢复未发布操作。

本地运行状态位于被 Git 忽略的 clone-local 目录。一个 clone 的多个 Worktree 由同一 Runtime 管理；其他 clone 不直接读取或写入本地状态。Git 才是协作记录的来源。

### 9.3 多用户边界

每位协作者在自己的 clone 运行。执行与 Gate 通过本地事务生效，需求采纳和精炼在提交本地 main 后生效，无 remote 或离线也使用相同规则；Git Remote 只异步同步历史，推送失败不撤销已完成操作。实时队列、Worker 状态和 Artifact 字节不随 Git 共享，后者通过独立交换包显式传递；尚未导入不等于运行失败，需要材料的审核与恢复须等待内容补齐。

有效性依据当前 clone 已知的 main；不强制 fetch。其它 clone 的正式更新进入本地 main 后重检基线及需求是否已采纳，输入变化需新 Run。独立需求没有修订合并或取代链；需求变化创建新 UUID，撤回成果可 Git revert，历史采纳不重新打开。Git 分叉和代码冲突按正常协作协调，不自动重放交付。界面按采纳顺序展示，编号仅作导航。系统不承诺离线 clone 间即时唯一或即时停止。

## 10. 一条完整需求的端到端示例

**需求**：登录失败五次后临时限制登录，并在界面上提示剩余等待时间。

1. 在本地起草并冻结独立需求，创建 Run ID、固定 source_commit 与 requirement_ref，在 detached Worktree 中执行；main 不变。
2. Workflow 根据 Feature、Layer 及适用的 Quality Source Facet 固定生成 Combination Facet 与 Combination Node DAG。
3. Runtime 找到 DAG 中当前就绪的 Combination Node；互不依赖的节点可以并行启动 Worker。
4. `Login × Domain`：Worker 的 Pre-Assess 发现规则需要变化，Agent 修改领域约束，生成 Commit，Gate 确认规则。
5. `Login × Application`：在 Domain 节点满足依赖后启动 Worker，读取 Domain 结果，更新 Use Case 与状态接口，生成 Commit 并审核。
6. `Login × Data`：在其前置依赖满足后判断需要保存失败次数，实现 Adapter 和测试，提交检查点。
7. `Login × Presentation`：在前置依赖满足后修改 BLoC/UI 状态与倒计时提示，经过 UI 对齐 Gate。
8. 如配置 Security/Accessibility 维度，相关 Combination Node 按固定 DAG 验证安全边界与界面可用性；Pre-Assess 判断适用性，明确不适用仍完成必要检查与 Gate。
9. 如果 UI Gate 发现 Domain 缺少某条业务规则，返回 `Login × Domain`，Runtime 重新启动对应 Worker，并让受影响的后继节点重新 Assess。
10. 执行集成测试，形成需求的最终候选版本；经人类确认后，以一个 squash Commit 同时将需求、代码、精简档案和回执提交 main，不追加回执提交。
11. 使用 Refinement 筛选返工记录，采纳并验证改进后清理已处理项。

这条流程最重要的特点是：**一个 Requirement 可以跨多个 Facet 逐步实现并反复需求对齐，但每次真正执行的都是一个明确的组合。**

## 11. 关键设计约束与风险

| 约束 / 风险 | 当前处理原则 |
|---|---|
| Combination Node 数量随 Facet 数量快速增加 | 定义阶段条件过滤生成较小的 Workflow 版本候选图；再用 Pre-Assess 避免每个节点都调用完整 Agent |
| 某些 Node 上下文互相冲突 | 阻塞或进入 Gate，不能隐式覆盖约束 |
| AI 开发者和 AI 审核者共同误解需求 | Gate 读取原始需求、已确认规则及独立验证证据 |
| 上游问题造成下游反复返工 | 精确指向上游 Combination Node，修复次数有上限，增量重新 Assess |
| 并行写入互相覆盖 | detached Worktree 隔离，Git Manager 受控合并 |
| 本地运行状态与 Git Commit 非原子 | 重启时核对 Git 引用、内容摘要和运行记录 |
| 容器访问主仓库和宿主机 | Rootless Podman + 最小权限挂载 + 宿主机 Git Manager |
| clone 间运行状态有延迟 | 本地状态留在 Runtime；执行与 Gate 本地保存，采纳时将必要摘要和依赖归档 main；未采纳记录显式导出快照 |

## 12. 第一版验证范围与设计入口

### 最小可验证闭环（MVP）

1. 定义两个 Source Facet，分别含少量只提供上下文的 Facet Node DAG。
2. 固定生成一个 Combination Facet 及其 Combination Node DAG；Runtime 按 DAG 找到就绪节点并允许无依赖分支并行。
3. 实现 Combination Worker 的 `Pre-Assess → Agent Execution → 本地 Checkpoint → 各 Node 的 Gate 全部批准`。
4. Gate 可定向返回上游 Combination Node；修复后重新执行受影响的下游节点。
5. 每个执行的 Attempt 使用独立 Worktree 和 Rootless Podman 环境；Runtime 持久化执行和 Gate，采纳时归档精简记录到 main。
6. Workflow 完成后运行集成验证，经人类确认，以一个 squash Commit 保存需求、代码、档案和回执。
7. WebUI 提供 Facet 编辑、组合预览、Gate 审核、执行历史与 Refinement。

### 详细设计入口

| 问题 | 权威定义 |
| --- | --- |
| Facet 顺序、组合、排除、上下文与 Scope | [Workflow](design/01-workflow.md) |
| 运行状态、成果接受与上游修复传播 | [Requirement](design/02-requirement.md) |
| 适用性、必要检查、代码汇聚与最终交付 | [Execution](design/04-execution.md) |
| Gate 与运行后的精炼 | [运行治理](design/03-governance.md) |
| 并发、容器、事务与 clone 协作 | [Services](design/05-services.md) |

精确影响分析、选择性重验证、多用户精细权限及长期治理等扩展统一见 [实现路线](plan.md)。

---

## 13. 最终总结

**总体模型**：

```text
Requirement
   ↓
main 固定输入 + detached Worktree
   ↓
Workflow Version
   ├─ Source Facet + Facet Node DAG
   ├─ Source Facet + Facet Node DAG
   └─ Combination Facet
       └─ Combination Node DAG
              ↓
       Workflow Runtime
              ↓ start
       Combination Worker per ready Node
              ↓
       Pre-Assess → Execute → Artifact → Git Commit → Post-Assess → Gate
              ↓                                      ↑
       后继节点就绪                         Gate 可返回上游 Node 修复
              ↓
集成验证 → 人类确认 → main → Refinement
```

> **最终原则**：**Source Facet 定义拆分维度，Facet Node 提供上下文，Combination Facet 承载派生执行图，Combination Node 才真正执行，Gate 持续对齐需求，Git 管理正式内容与已发布证据历史，Workflow Runtime 只负责调度和监督 Combination Worker。**

该设计以**最少的自研基础设施**实现**多维需求对齐、AI 自主执行、人类确认与运行精炼、Git 原生并行和故障恢复**。它是一份可以开始原型验证的系统构想，而非已经被生产实践证明的最终架构。

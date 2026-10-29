# 多切面组合执行的 AI 软件工程系统

**产品构想与总体架构整理稿 · v0.2**

**整理日期：2026 年 10 月 29 日**  
**文档定位：设计共识与后续研发基线；不是最终接口规范。**

> **一句话定义**：一个通过多个 Source Facet 及其内部 Node DAG 从多个维度拆解软件，在派生的 Combination Node DAG 中执行 AI 开发，并通过可委托 Gate 持续进行需求对齐的 Git 原生自动化软件工程系统。

## 0. 阅读指引与决策状态

这份文档优先整理**已经明确的想法**，不为了完整而引入新的复杂抽象。凡仍属于实现建议或尚未定论的事项，分别标注为「建议」或「待确认」。

- **已明确**：Source Facet 内部通过 Node DAG 表达上下文与执行依赖；Facet 之间不建立边；Workflow 版本内固定派生 Combination Facet；Combination Node 是真正的执行单元；合并后的 Combination Node DAG 决定执行顺序并允许无依赖分支并行；Workflow Runtime 只负责启动和监督 Combination Worker；Gate 可人工或 AI 代理；Git Branch + Worktree 进行需求隔离；不自建 Artifact 版本管理；不设独立 AI 智能调度器。
- **已形成的方案倾向**：WebUI + 后台运行时、无头部署；SQLite 管理本地状态；Podman 隔离 Agent；每次有效 Combination Node 修改创建 Git Commit，最终以 Squash Merge 交付主分支。
- **尚待验证**：Facet 条件适用性的完整规则、并发上限与并行分支的 Git 集成策略、Gate 回退影响范围的精确计算、多用户/多实例共享运行状态。

---

## 1. 出发点与目标

### 1.1 核心判断

AI 的代码生成能力不断提高，但快速生成 Demo 并不等于长期可维护、安全稳健的软件。开发过程还必须将人的真实目标与 AI 的设计和实现反复对齐。即使 AI 能自行发现问题和提出下级需求，系统仍需要清晰的人类目标、授权边界和决策依据。

### 1.2 四个目标

1. **更少的人工成本**：人工集中处理高价值的需求、设计和风险决策，其余 Gate 可以委托 AI。
2. **更快的开发速度**：多个 Requirement 并行；在组合中先 Assess，避免不必要的实际修改。
3. **长期可维护**：按架构与 Feature 等维度持续对齐，保持接口、模块边界及整体行为一致。
4. **安全稳健**：容器隔离、自动测试、可追踪 Gate 决策、Git 检查点与安全合并。

**研发理念**：减少人类对代码实现细节的持续监督，增强人类对目标、关键设计与授权范围的控制。

## 2. 核心概念：理解系统所需的主要对象

| 概念 | 定义 | 是否执行开发任务 |
|---|---|---|
| **Requirement（需求）** | 一次开发目标；通常对应独立 Git 分支及 Worktree | 否，驱动执行 |
| **Workflow（工作流）** | 定义 Source Facet、Facet Node DAG、Combination Facet 及其生成规则的版本化结构 | 由 Runtime 运行 |
| **Source Facet（源切面）** | 用户定义的一个拆分维度，内部包含 Facet Node DAG，例如 Feature、Layer | 否 |
| **Facet Node（切面节点）** | Source Facet 中的上下文节点，提供范围、规则、输入和约束 | **否，绝不单独执行** |
| **Combination Facet（组合切面）** | 由多个 Source Facet 派生的执行切面；在 Workflow 版本内固定 | 否，承载执行图 |
| **Combination Node（组合节点）** | 从每个 Source Facet 选择一个 Facet Node 形成的节点，属于 Combination Node DAG | **是，唯一的业务执行单元** |
| **Combination Worker（组合执行器）** | Runtime 为 Combination Node 启动的进程或容器，负责一次实际执行 | 执行 Combination Node |
| **Gate（决策关卡）** | 针对组合执行成果的需求对齐、验收或授权 | 作为组合执行的一部分 |

**Artifact** 不是独立版本化的核心实体，而是组合执行过程中产生和传递的文件、规范、代码、报告等中间成果，由 Git 承担其正式历史管理。

### 2.1 特别重要的边界

- Facet Node **只提供上下文**，不拥有自己的独立 Agent 执行、Artifact 生产或 Gate 审批生命周期。
- 每个 Source Facet 都有自己的 Node DAG；Source Facet 之间不建立 DAG 边。
- Combination Facet 是由多个 Source Facet 派生出的执行 Facet，不引入新的业务维度，也不由用户直接维护节点。
- Combination Node 是从每个 Source Facet 选择一个 Facet Node 后形成的组合执行上下文，也是 Combination Node DAG 中的真实业务节点。
- 每个 Combination Node 在完整上下文中由 Combination Worker 运行 Assess → Execution（必要时）→ Artifact/Git Checkpoint → Gate。
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

Facet 内的边同时表示：

- 后继 Node 可以读取前驱 Node 的定义或成果；
- 在同一需求和同一组其他 Facet 选择下，前驱对应的 Combination Node 必须先完成或达到可继续的状态。

Source Facet 之间不建立边。Feature 的分支不会因为 Layer 的分支而合并成一条人工指定的线性顺序。

### 3.2 Combination Facet 与 Combination Node DAG

Workflow 固定版本中的多个 Source Facet 派生出一个 Combination Facet。Combination Facet 不增加新的业务维度，而是承载由 Combination Node 构成的执行图。

从每个 Source Facet 选择一个真实 Facet Node，形成一个 Combination Node：

```text
Login × Domain
Login × Application
Login × Presentation
```

对于任意 Source Facet 中的边 `u → v`，在其他 Facet 的选择保持不变时，向 Combination Node DAG 提升对应的边：

```text
(..., u, ...) → (..., v, ...)
```

因此上面的两个 Source Facet 会形成：

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

Combination Facet 在 Workflow 版本内固定。Requirement 启动时创建该 Combination Facet 的运行实例，记录上下文快照、执行状态和结果，但不重新定义另一张结构不同的 DAG。Workflow 修改后产生新版本，已有运行继续使用原版本。

### 3.3 两个典型 Source Facet

**Feature Facet**（功能维度）可以包括：登录、通知、个人中心。  
**Layer Facet**（架构维度）可以包括：Presentation、Application、Domain、Data。

`Login × Domain` 是一个 Combination Node，表示：**在登录 Feature 的业务范围中，按照 Domain 层职责和约束，判断、设计和实现本次相关修改。**

`Login × Presentation` 则表示：同一个登录 Feature，在 Presentation 层的具体设计与实现。

也可以在后续增加 Quality Facet（Security、Accessibility、Performance 等），而不需要发明新的底层 Node 类型。

### 3.4 组合上下文的构成

一个组合运行时读取：

- 原始 Requirement 与已确认的需求约束；
- Workflow 的全局规则；
- 当前 Combination Node 选中的各 Source Facet Node 上下文（例如 Login + Domain）；
- 当前 Requirement Worktree 的代码、历史与已产出的 Artifact 引用；
- 适用的权限、环境与 Gate 策略。

**原则**：上下文是层层绑定的；不同 Node 的约束冲突时不能默默以后者覆盖前者，应暂停并进入评估或 Gate。

### 3.5 条件适用性（方案建议）

Combination Facet 的结构在 Workflow 版本内固定，但并非每个 Combination Node 都必然对每个 Requirement 产生实际执行。运行时可以根据需求上下文对节点进行适用性评估，避免无意义的 Agent 启动。

例如：

- `Login × Presentation × Accessibility`：通常适用；
- `Login × Domain × Accessibility`：一般不需要专门的 UI 无障碍检查；
- 认证、授权及敏感数据相关组合：需考虑 Security 检查。

适用性评估的结果状态、依赖满足规则和后继节点如何处理，暂不在本轮固定。可以先从静态条件 + Combination Worker 的 Pre-Assess 开始。无法可靠判断是否适用时，不应默认跳过关键检查；安全底线不应仅靠 Feature 名称决定。

## 4. Combination Node 与 Combination Worker：真正的执行单元

Combination Node 是静态的业务执行节点；Combination Worker 是 Runtime 为它启动的一次实际进程或容器。Worker 负责一个 Combination Node 的完整执行生命周期，Runtime 不直接执行 Agent、命令或代码修改。

每个 Combination Worker 遵循统一的执行协议：

```text
Combination Node 输入上下文
    ↓
Pre-Assess：是否相关、是否需要修改、输入是否充分
    ↓
Execution（可跳过）：Agent / Command / Tool
    ↓
Artifact：输出文件、规范、代码、报告
    ↓
Git Stage → Git Commit（有实际变更时）
    ↓
Post-Assess：完整性、额外影响、上游问题
    ↓
Gate（可配置）：Human / AI Proxy / Automatic
    ↓
Approved → DAG 中的后继节点可能就绪；Rejected → 修复相关 Combination Node
```

Runtime 根据 Combination Node DAG 找到所有前置节点已经满足依赖的节点，并在并发限制内启动多个 Combination Worker。没有路径关系的 Combination Node 可以并行；有多个前置节点的节点必须等待所有前置节点完成或达到可继续状态。

建议的运行记录层次为：

```text
Combination Node       // Workflow 版本中的静态节点
Combination Node Run   // 某次 Requirement 运行中的节点记录
Combination Attempt    // 一次实际尝试或重试
Combination Worker     // 承载 Attempt 的进程或容器
```

### 4.1 Pre-Assess

在当前 Combination Node 的职责范围内判断：

- 是否与本需求有关；
- 需不需要修改现有工程文件；
- 缺少哪些输入、契约或上游设计；
- 是否触及更高风险、需要额外审核。

若 Pre-Assess 判定不需要修改，可以跳过 Agent 执行和 Commit；是否仍需执行 Gate 或验证，以及该结果的正式状态名称，留待后续状态设计。

### 4.2 Execution 与 Artifact

Combination Worker 中的 Agent 在隔离环境中操作**当前 Requirement 的 Worktree**。Artifact 可以是 Markdown 规范、接口 Schema、源码、测试报告、原型等。Combination Node 之间传递的主要是**路径和 Git 内容引用**，而不是复制一套独立 Artifact 数据库。

### 4.3 Post-Assess 与 Gate

Post-Assess 检查是否遗漏相关变更、是否引入其他模块影响。Gate 决定是否接受该组合成果、继续执行、返回上游组合或请求人工。

**Facet Node 没有自己的 Gate**；Gate 属于 Combination Node 的执行策略，可按组合上下文覆盖默认规则。

## 5. Gate：可委托的需求对齐机制

Gate 的目标不仅是代码质量，更是持续地与人类需求、架构要求和整体 Feature 行为对齐。Gate 可以设置得较密集，但不应强迫人类审批每一次结果。

| 模式 | 决策主体 | 典型场景 |
|---|---|---|
| **Human** | 人类 | 新需求、重要架构争议、风险较高的授权 |
| **AI Proxy** | 受委托的独立 AI 审核者 | 常规设计对齐、跨层一致性、阶段验收 |
| **Automatic** | 规则或测试 | 结构检查、测试通过、格式与接口兼容性 |

WebUI 应支持**一键委托 AI**与**人工接管**。委托的对象是 Gate 决策，不是无限制地授予 Agent 权限。

Gate 结果至少包括：`Approved`、`Rejected`、`Escalated`、`Blocked`。拒绝时可指向具体的**上游 Combination Node**，而不是笼统地退回某个 Source Facet Node。

所有 Gate 决策应关联已评估的 Git Commit / Tree 和上下文规则，防止文件变化后继续复用旧批准。对于敏感操作，保留不可跳过的权限边界。

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

**默认策略**：Gate 指定目标 Combination Node，Workflow Runtime 重新启动该节点的 Combination Worker；Agent 基于当前分支**向前修复并追加 Commit**。历史不删除，其他成果可尽量复用。

**特殊策略**：如果设计方向需要整体放弃，可从旧检查点创建新的修复分支/Worktree，保留原历史作参考；不默认执行破坏性的 `git reset --hard`。

**尚待设计**：回退后哪些组合必须重新执行。最简单的第一版规则是从受影响组合向后重新 Assess；之后再依据显式依赖减少重跑范围。需要重试上限，避免无限来回。

## 7. Git：唯一的工程版本管理系统

### 7.1 需求并行

```text
main 工作区（稳定基线；Agent 不直接修改）
     │
     ├── feature/REQ-101 → 独立 Worktree → 多个组合执行
     ├── feature/REQ-102 → 独立 Worktree → 多个组合执行
     └── feature/REQ-103 → 独立 Worktree → 多个组合执行
```

- 不同 Requirement 的开发独立进行。
- Combination Node DAG 中没有依赖路径的节点可以并行启动 Worker。
- 同一 Requirement 内并行写入的 Combination Node 使用隔离的临时 Worktree/Branch，完成后由 Git Manager 集成；有依赖的后继节点等待合并后的共同快照。
- Git 管理历史、分支、Diff、Merge、Revert、Tag；**不开发第二套 Artifact 版本系统**。

### 7.2 组合级检查点与交付

1. Combination Node 产生修改后，可信 Git Manager 检查允许修改的文件并执行 `git add`。
2. 对实际变更创建 **Combination Node Commit**，保存本次执行检查点；没有实际变更时不强制创建空提交。
3. Gate 对已锁定的内容快照作决策；被拒绝的版本仍可以保留用于修复追踪。
4. Requirement 完成后，在集成环境进行验证，通过 **Squash Merge** 将一个需求的最终变更合并到 main。
5. 开发分支可按保留策略归档；如果需要长期追踪组合级历史，应保留可达的 Git 引用，避免对象被清理。

**不把 Git Stash 作为常规产物生命周期管理工具。** Stash 适合临时搁置工作，Commit 更适合 Gate 追踪、恢复和多人协作。

### 7.3 主工作区保护

Agent 不直接修改 main Worktree；Git 合并与主分支更新由宿主机可信 Git Manager 完成。容器内不开放可写的共享 `.git` 元数据及 Podman 管理 Socket。Worktree 本身不是绝对安全边界，需靠执行权限与容器挂载限制加固。

## 8. Podman：隔离 Agent 与开发环境

建议默认使用 **Rootless Podman**，按 Requirement 提供独立容器运行环境：

- 串行执行的 Combination Worker 可以复用同需求容器；等待 Gate 时可停止容器；完成需求后删除容器。
- 一次性测试或高敏感检查可用 `--rm` 临时容器。
- 并行写入的 Combination Worker 使用独立 Worktree + 容器。
- 代码和 Artifact 在 Git Worktree，工具链在镜像，依赖缓存可在受控 Volume；容器内部临时状态不应成为唯一结果来源。
- Git Stage/Commit/Merge 由宿主机可信 Git Manager 负责，不让 Agent 拥有跨分支修改权限。
- Android 模拟器、设备/KVM 等特殊测试任务可使用单独受控的执行环境，不给普通编码 Agent 默认特权容器。

## 9. WebUI、无头 Runtime 与 SQLite

### 9.1 产品形态

采用**WebUI + 后台 Runtime**，本地或 Linux 无头服务器均可运行。关闭浏览器或 SSH 连接后，Workflow 仍可继续执行。

- **WebUI**：Source Facet / Facet Node 编辑器、Combination Facet 与 Combination Node DAG 预览、Git Diff、日志、Gate 委托/接管、运行监控。
- **Workflow Runtime**：读取 Combination Node DAG，判断就绪节点，启动和监督 Combination Worker，处理依赖、有限并行、失败恢复与 Gate 流转，**不另设 AI 智能调度器**。
- **Combination Worker / Agent Adapter**：由 Runtime 启动，调用 Codex 等 Agent 或命令行工具，负责一个 Combination Node 的实际生命周期。
- **Git Manager / Podman Manager**：提供经过权限控制的宿主机操作。

技术倾向：Rust + Axum；前端 React + React Flow。这些是建议选型，不是核心领域语义。

### 9.2 状态存储

SQLite 保存需求、WorkflowRun、CombinationNodeRun、CombinationAttempt、执行状态、Gate 决策、Git Commit 引用与日志位置。文件内容继续由 Git/文件系统负责。

本地状态可保存在被 Git 忽略的 dot directory，例如 `.ai-local/state.sqlite`；但实际部署需防止被清理命令删除，并做一致性备份。一个项目的多个 Worktree 应由**同一个受控 Runtime**访问该项目的状态库，不让 Agent 直接改写 Gate 审批数据。

### 9.3 多用户边界

初期可先实现单 Owner、多设备访问。Git Remote 足以同步代码、规范与 Workflow 文件，但**不能直接同步本地 SQLite 的正在运行状态**。是否提供完整多人共用同一个实例、角色和审批权限，仍待决定；数据结构预留 Actor 与授权范围即可。

## 10. 一条完整需求的端到端示例

**需求**：登录失败五次后临时限制登录，并在界面上提示剩余等待时间。

1. 创建 `feature/REQ-101` 和独立 Worktree，绑定 Workflow 版本。
2. Workflow 根据 Feature、Layer 及适用的 Quality Source Facet 固定生成 Combination Facet 与 Combination Node DAG。
3. Runtime 找到 DAG 中当前就绪的 Combination Node；互不依赖的节点可以并行启动 Worker。
4. `Login × Domain`：Worker 的 Pre-Assess 发现规则需要变化，Agent 修改领域约束，生成 Commit，Gate 确认规则。
5. `Login × Application`：在 Domain 节点满足依赖后启动 Worker，读取 Domain 结果，更新 Use Case 与状态接口，生成 Commit 并审核。
6. `Login × Data`：在其前置依赖满足后判断需要保存失败次数，实现 Adapter 和测试，提交检查点。
7. `Login × Presentation`：在前置依赖满足后修改 BLoC/UI 状态与倒计时提示，经过 UI 对齐 Gate。
8. 适用的 Security/Accessibility Combination Node 分别验证安全边界与界面可用性；适用性处理规则另行设计。
9. 如果 UI Gate 发现 Domain 缺少某条业务规则，返回 `Login × Domain`，Runtime 重新启动对应 Worker，并让受影响的后继节点重新 Assess。
10. 执行集成测试，形成需求的最终候选版本；通过受控 Squash Merge 合并到 main。

这条流程最重要的特点是：**一个 Requirement 可以跨多个 Facet 逐步实现并反复需求对齐，但每次真正执行的都是一个明确的组合。**

## 11. 关键设计约束与风险

| 约束 / 风险 | 当前处理原则 |
|---|---|
| Combination Node 数量随 Facet 数量快速增加 | Workflow 版本固定候选图；适用性规则 + Pre-Assess；避免每个节点都调用完整 Agent |
| 某些 Node 上下文互相冲突 | 阻塞或进入 Gate，不能隐式覆盖约束 |
| AI 开发者和 AI 审核者共同误解需求 | Gate 读取原始需求、已确认规则及独立验证证据 |
| 上游问题造成下游反复返工 | 精确指向上游 Combination Node，修复次数有上限，增量重新 Assess |
| 并行写入互相覆盖 | Git Worktree/Branch 隔离，Git Manager 受控合并 |
| SQLite 记录与 Git Commit 非原子 | 重启时核对 Git 引用、内容摘要和运行记录 |
| 容器访问主仓库和宿主机 | Rootless Podman + 最小权限挂载 + 宿主机 Git Manager |
| 多人远程 Git 合并后运行记录不共享 | Git 只同步工程成果；共享 Gate/执行状态属于未来协作扩展 |

## 12. 第一版验证范围与待确认事项

### 最小可验证闭环（MVP）

1. 定义两个 Source Facet，分别含少量只提供上下文的 Facet Node DAG。
2. 固定生成一个 Combination Facet 及其 Combination Node DAG；Runtime 按 DAG 找到就绪节点并允许无依赖分支并行。
3. 实现 Combination Worker 的 `Pre-Assess → Agent Execution → Git Commit → AI/Human Gate`。
4. Gate 可定向返回上游 Combination Node；修复后重新执行受影响的下游节点。
5. 每个 Requirement 独立 Worktree 和 Rootless Podman；SQLite 记录运行与审批。
6. Workflow 完成后运行集成验证，并 Squash Merge 到 main。
7. WebUI 提供 Facet 编辑、组合预览、Gate 接管与执行历史。

### 仍待明确（不要误认作既定设计）

- **Facet 适用性规则**：条件表达式、AI 辅助适用性判断及“不确定”的处理边界。
- **Combination Node 状态**：`Not Applicable`、`No Change`、`Approved` 等状态的精确定义，以及状态如何满足后继依赖。
- **并行集成策略**：并发上限、并行 Worker 的 Worktree 合并、冲突处理和汇合节点的共同快照。
- **上下文来源与优先级**：不同 Node 的输入和约束冲突时的确定流程。
- **回退影响分析**：先采取保守重评估，再逐步建立精确依赖。
- **多用户**：只需多个浏览器控制同一 Owner 的实例，还是需要真正的多人审批与权限分离。

---

## 13. 最终总结

**总体模型**：

```text
Requirement
   ↓
Git Requirement Branch + Worktree
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
集成验证 → Squash Merge → main
```

> **最终原则**：**Source Facet 定义拆分维度，Facet Node 提供上下文，Combination Facet 承载派生执行图，Combination Node 才真正执行，Gate 持续对齐需求，Git 管理全部工程历史，Workflow Runtime 只负责调度和监督 Combination Worker。**

该设计以**最少的自研基础设施**实现**多维需求对齐、AI 自主执行、可委托审批、Git 原生并行和故障恢复**。它是一份可以开始原型验证的系统构想，而非已经被生产实践证明的最终架构。

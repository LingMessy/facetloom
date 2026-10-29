# 多切面组合执行的 AI 软件工程系统

**产品构想与总体架构整理稿 · v0.1**  
**整理日期：2026 年 10 月 29 日**  
**文档定位：设计共识与后续研发基线；不是最终接口规范。**

> **一句话定义**：一个通过有序 Facet 从多个维度拆解软件，在 Facet Node 的组合上下文中执行 AI 开发，并通过可委托 Gate 持续进行需求对齐的 Git 原生自动化软件工程系统。

## 0. 阅读指引与决策状态

这份文档优先整理**已经明确的想法**，不为了完整而引入新的复杂抽象。凡仍属于实现建议或尚未定论的事项，分别标注为「建议」或「待确认」。

- **已明确**：有序 Facet；Node 只提供上下文；**Combination 才是真正的执行单元**；Gate 可人工或 AI 代理；Git Branch + Worktree 进行需求隔离；不自建 Artifact 版本管理；不设独立 AI 智能调度器。
- **已形成的方案倾向**：WebUI + 后台运行时、无头部署；SQLite 管理本地状态；Podman 隔离 Agent；每次有效组合修改创建 Git Commit，最终以 Squash Merge 交付主分支。
- **尚待验证**：Facet 条件展开的完整规则、多组合并行策略、Gate 回退影响范围的精确计算、多用户/多实例共享运行状态。

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

## 2. 核心概念：六个词足够理解系统

| 概念 | 定义 | 是否执行开发任务 |
|---|---|---|
| **Requirement（需求）** | 一次开发目标；通常对应独立 Git 分支及 Worktree | 否，驱动执行 |
| **Workflow（工作流）** | 由多个**有顺序的 Facet** 构成的执行结构 | 由运行时展开 |
| **Facet（切面）** | 对软件进行拆分、理解与需求对齐的一个维度 | 否 |
| **Node（节点）** | Facet 中的一个上下文选项，提供范围、规则、输入和约束 | **否，绝不单独执行** |
| **Combination（组合）** | 每个 Facet 各选一个 Node 得到的**组合执行上下文** | **是，唯一的业务执行单元** |
| **Gate（决策关卡）** | 针对组合执行成果的需求对齐、验收或授权 | 作为组合执行的一部分 |

**Artifact** 不是独立版本化的核心实体，而是组合执行过程中产生和传递的文件、规范、代码、报告等中间成果，由 Git 承担其正式历史管理。

### 2.1 特别重要的边界

- Node **只提供上下文**，不拥有自己的独立 Agent 执行、Artifact 生产或 Gate 审批生命周期。
- 每一个**组合**在完整上下文中运行 Assess → Execution（必要时）→ Artifact/Git Checkpoint → Gate。
- Facet 是**执行维度**，不只是 Node 的一个标签；多个 Facet 共同决定实际工作范围。
- 独立的 AI Scheduler 不负责预先分析并分配全部需求。只保留轻量的 Workflow Runtime 做顺序、依赖、重试与恢复。

## 3. Facet：有序维度与组合执行

### 3.1 基本规则

假设 Facet X 有 `x1, x2, x3`，Facet Y 有 `y1, y2, y3`。默认执行顺序为：

```text
x1y1 → x1y2 → x1y3
   ↓
x2y1 → x2y2 → x2y3
   ↓
x3y1 → x3y2 → x3y3
```

也就是固定外层 `x1`，依次遍历整个 Y，然后进入 `x2`。扩展到三个或更多 Facet 时继续做有序嵌套。数学上相当于对有序集合的笛卡尔积进行**字典序遍历**。

```python
for x in feature_facet.nodes:
    for y in layer_facet.nodes:
        run_combination(context=(requirement, x, y))
```

`run_combination` 执行的是 **x 和 y 组成的一个工作上下文**，而不是先运行 x 再运行 y。外层 Node 的工作只是提供 Feature 需求与限制，内层 Node 提供 Layer 规则与范围。

### 3.2 两个典型 Facet

**Feature Facet**（功能维度）可以包括：登录、通知、个人中心。  
**Layer Facet**（架构维度）可以包括：Presentation、Application、Domain、Data。

`Login × Domain` 表示：**在登录 Feature 的业务范围中，按照 Domain 层职责和约束，判断、设计和实现本次相关修改。**

`Login × Presentation` 则表示：同一个登录 Feature，在 Presentation 层的具体设计与实现。

也可以在后续增加 Quality Facet（Security、Accessibility、Performance 等），而不需要发明新的底层 Node 类型。

### 3.3 组合上下文的构成

一个组合运行时读取：

- 原始 Requirement 与已确认的需求约束；
- Workflow 的全局规则；
- 当前选中的各 Facet Node 上下文（例如 Login + Domain）；
- 当前 Requirement Worktree 的代码、历史与已产出的 Artifact 引用；
- 适用的权限、环境与 Gate 策略。

**原则**：上下文是层层绑定的；不同 Node 的约束冲突时不能默默以后者覆盖前者，应暂停并进入评估或 Gate。

### 3.4 条件展开（方案建议）

完整笛卡尔积可能产生大量无关组合，因此支持**按适用性选择组合**。

例如：

- `Login × Presentation × Accessibility`：通常适用；
- `Login × Domain × Accessibility`：一般不需要专门的 UI 无障碍检查；
- 认证、授权及敏感数据相关组合：需考虑 Security 检查。

区分三类结果：

| 结果 | 含义 |
|---|---|
| **Not Applicable** | 组合不属于本次适用范围，不展开 |
| **No Change** | 组合适用，但 Assess 后确定无需改动 |
| **Executed** | 组合适用，且实际执行并产生工作结果 |

无法可靠判断是否适用时，不应默认跳过关键检查；可进入 Assess 或 Gate。安全底线不应仅靠 Feature 名称决定。

**尚未决定**：适用性规则是以配置条件为主，还是允许 AI 在扩展时参与判定；初版可从静态条件 + 组合 Pre-Assess 开始。

## 4. Combination：真正的执行单元

每个组合遵循统一的执行协议：

```text
组合输入上下文
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
Approved → 下一个组合；Rejected → 修复相关组合
```

### 4.1 Pre-Assess

在当前组合的职责范围内判断：

- 是否与本需求有关；
- 需不需要修改现有工程文件；
- 缺少哪些输入、契约或上游设计；
- 是否触及更高风险、需要额外审核。

若返回 `No Change`，可以跳过 Agent 执行和 Commit，但按配置仍可能需要执行 Gate 或验证。

### 4.2 Execution 与 Artifact

Agent 在隔离环境中操作**当前 Requirement 的 Worktree**。Artifact 可以是 Markdown 规范、接口 Schema、源码、测试报告、原型等。组合间传递的主要是**路径和 Git 内容引用**，而不是复制一套独立 Artifact 数据库。

### 4.3 Post-Assess 与 Gate

Post-Assess 检查是否遗漏相关变更、是否引入其他模块影响。Gate 决定是否接受该组合成果、继续执行、返回上游组合或请求人工。

**Node 没有自己的 Gate**；Gate 属于组合执行策略，可按组合上下文覆盖默认规则。

## 5. Gate：可委托的需求对齐机制

Gate 的目标不仅是代码质量，更是持续地与人类需求、架构要求和整体 Feature 行为对齐。Gate 可以设置得较密集，但不应强迫人类审批每一次结果。

| 模式 | 决策主体 | 典型场景 |
|---|---|---|
| **Human** | 人类 | 新需求、重要架构争议、风险较高的授权 |
| **AI Proxy** | 受委托的独立 AI 审核者 | 常规设计对齐、跨层一致性、阶段验收 |
| **Automatic** | 规则或测试 | 结构检查、测试通过、格式与接口兼容性 |

WebUI 应支持**一键委托 AI**与**人工接管**。委托的对象是 Gate 决策，不是无限制地授予 Agent 权限。

Gate 结果至少包括：`Approved`、`Rejected`、`Escalated`、`Blocked`。拒绝时可指向具体的**上游组合**，而不是笼统地退回某个 Node。

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

**默认策略**：Gate 指定目标组合，Workflow Runtime 重新执行该组合；Agent 基于当前分支**向前修复并追加 Commit**。历史不删除，其他成果可尽量复用。

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
- 同一 Requirement 的串行组合可以复用 Worktree。
- 同一 Requirement 内**并行写入**的组合使用隔离的临时 Worktree/Branch，完成后由 Git Manager 集成。
- Git 管理历史、分支、Diff、Merge、Revert、Tag；**不开发第二套 Artifact 版本系统**。

### 7.2 组合级检查点与交付

1. 组合产生修改后，可信 Git Manager 检查允许修改的文件并执行 `git add`。
2. 对实际变更创建 **Combination Commit**，保存本次执行检查点；`No Change` 不强制空提交。
3. Gate 对已锁定的内容快照作决策；被拒绝的版本仍可以保留用于修复追踪。
4. Requirement 完成后，在集成环境进行验证，通过 **Squash Merge** 将一个需求的最终变更合并到 main。
5. 开发分支可按保留策略归档；如果需要长期追踪组合级历史，应保留可达的 Git 引用，避免对象被清理。

**不把 Git Stash 作为常规产物生命周期管理工具。** Stash 适合临时搁置工作，Commit 更适合 Gate 追踪、恢复和多人协作。

### 7.3 主工作区保护

Agent 不直接修改 main Worktree；Git 合并与主分支更新由宿主机可信 Git Manager 完成。容器内不开放可写的共享 `.git` 元数据及 Podman 管理 Socket。Worktree 本身不是绝对安全边界，需靠执行权限与容器挂载限制加固。

## 8. Podman：隔离 Agent 与开发环境

建议默认使用 **Rootless Podman**，按 Requirement 提供独立容器运行环境：

- 串行组合默认复用同需求容器；等待 Gate 时可停止容器；完成需求后删除容器。
- 一次性测试或高敏感检查可用 `--rm` 临时容器。
- 并行写入组合使用独立 Worktree + 容器。
- 代码和 Artifact 在 Git Worktree，工具链在镜像，依赖缓存可在受控 Volume；容器内部临时状态不应成为唯一结果来源。
- Git Stage/Commit/Merge 由宿主机可信 Git Manager 负责，不让 Agent 拥有跨分支修改权限。
- Android 模拟器、设备/KVM 等特殊测试任务可使用单独受控的执行环境，不给普通编码 Agent 默认特权容器。

## 9. WebUI、无头 Runtime 与 SQLite

### 9.1 产品形态

采用**WebUI + 后台 Runtime**，本地或 Linux 无头服务器均可运行。关闭浏览器或 SSH 连接后，Workflow 仍可继续执行。

- **WebUI**：Facet / Node 编辑器、组合矩阵预览、Git Diff、日志、Gate 委托/接管、运行监控。
- **Runtime**：只负责编排组合顺序、依赖、失败恢复、有限并行与 Gate 流转，**不另设 AI 智能调度器**。
- **Agent Adapter**：调用 Codex 等 Agent 或命令行工具。
- **Git Manager / Podman Manager**：提供经过权限控制的宿主机操作。

技术倾向：Rust + Axum；前端 React + React Flow。这些是建议选型，不是核心领域语义。

### 9.2 状态存储

SQLite 保存需求、WorkflowRun、CombinationRun、Attempt、执行状态、Gate 决策、Git Commit 引用与日志位置。文件内容继续由 Git/文件系统负责。

本地状态可保存在被 Git 忽略的 dot directory，例如 `.ai-local/state.sqlite`；但实际部署需防止被清理命令删除，并做一致性备份。一个项目的多个 Worktree 应由**同一个受控 Runtime**访问该项目的状态库，不让 Agent 直接改写 Gate 审批数据。

### 9.3 多用户边界

初期可先实现单 Owner、多设备访问。Git Remote 足以同步代码、规范与 Workflow 文件，但**不能直接同步本地 SQLite 的正在运行状态**。是否提供完整多人共用同一个实例、角色和审批权限，仍待决定；数据结构预留 Actor 与授权范围即可。

## 10. 一条完整需求的端到端示例

**需求**：登录失败五次后临时限制登录，并在界面上提示剩余等待时间。

1. 创建 `feature/REQ-101` 和独立 Worktree，绑定 Workflow 定义。
2. 按 Facet 顺序枚举 Feature × Layer ×（适用时）Quality 的组合。
3. `Login × Domain`：Pre-Assess 发现规则需要变化，Agent 修改领域约束，生成 Commit，Gate 确认规则。
4. `Login × Application`：读取 Domain 结果，更新 Use Case 与状态接口，生成 Commit 并审核。
5. `Login × Data`：判断需要保存失败次数，实现 Adapter 和测试，提交检查点。
6. `Login × Presentation`：修改 BLoC/UI 状态与倒计时提示，经过 UI 对齐 Gate。
7. 适用的 Security/Accessibility 组合分别验证安全边界与界面可用性；无关组合跳过。
8. 如果 UI Gate 发现 Domain 缺少某条业务规则，返回 `Login × Domain`，向前修复并让受影响组合重新 Assess。
9. 执行集成测试，形成需求的最终候选版本；通过受控 Squash Merge 合并到 main。

这条流程最重要的特点是：**一个 Requirement 可以跨多个 Facet 逐步实现并反复需求对齐，但每次真正执行的都是一个明确的组合。**

## 11. 关键设计约束与风险

| 约束 / 风险 | 当前处理原则 |
|---|---|
| 组合数量随 Facet 数量快速增加 | 条件展开 + Pre-Assess；避免每个组合都调用完整 Agent |
| 某些 Node 上下文互相冲突 | 阻塞或进入 Gate，不能隐式覆盖约束 |
| AI 开发者和 AI 审核者共同误解需求 | Gate 读取原始需求、已确认规则及独立验证证据 |
| 上游问题造成下游反复返工 | 精确指向上游组合，修复次数有上限，增量重新 Assess |
| 并行写入互相覆盖 | Git Worktree/Branch 隔离，Git Manager 受控合并 |
| SQLite 记录与 Git Commit 非原子 | 重启时核对 Git 引用、内容摘要和运行记录 |
| 容器访问主仓库和宿主机 | Rootless Podman + 最小权限挂载 + 宿主机 Git Manager |
| 多人远程 Git 合并后运行记录不共享 | Git 只同步工程成果；共享 Gate/执行状态属于未来协作扩展 |

## 12. 第一版验证范围与待确认事项

### 最小可验证闭环（MVP）

1. 定义两个有序 Facet，分别含少量只提供上下文的 Node。
2. 由 Runtime 自动展开组合，并实现确定的字典序执行和条件跳过。
3. 实现组合 `Pre-Assess → Agent Execution → Git Commit → AI/Human Gate`。
4. Gate 可定向返回上游组合；修复后重新执行受影响的下游组合。
5. 每个 Requirement 独立 Worktree 和 Rootless Podman；SQLite 记录运行与审批。
6. Workflow 完成后运行集成验证，并 Squash Merge 到 main。
7. WebUI 提供 Facet 编辑、组合预览、Gate 接管与执行历史。

### 仍待明确（不要误认作既定设计）

- **Facet 展开规则**：条件表达式、AI 辅助适用性判断及“不确定”的处理边界。
- **组合并行**：目前以字典序为默认；未来哪些组合可以并行，如何识别依赖。
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
Workflow = Ordered Facets
   ↓
每个 Facet 选择一个只提供上下文的 Node
   ↓
Combination Execution Context
   ↓
Pre-Assess → Execute → Artifact → Git Commit → Post-Assess → Gate
   ↓                        ↑
继续下一组合       Gate 可返回上游组合进行修复
   ↓
集成验证 → Squash Merge → main
```

> **最终原则**：**Facet 定义拆分维度，Node 提供上下文，Combination 才真正执行，Gate 持续对齐需求，Git 管理全部工程历史，Workflow Runtime 只做必要的流程控制。**

该设计以**最少的自研基础设施**实现**多维需求对齐、AI 自主执行、可委托审批、Git 原生并行和故障恢复**。它是一份可以开始原型验证的系统构想，而非已经被生产实践证明的最终架构。

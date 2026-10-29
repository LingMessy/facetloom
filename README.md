# FacetLoom · 维织

**Multi-Facet AI Engineering Studio**

FacetLoom 是一个从需求到可审核代码变更的 AI 软件工程系统。它为 Agent 提供有边界的上下文和修改范围，为执行保留 Git 检查点，并通过 Gate 持续检查实现是否符合需求和架构约束。

> 需求有去向，任务有边界，产物有证据。

## 核心模型

Workflow 定义多个 Source Facet。每个 Source Facet 内部通过 Node DAG 表达上下文和执行依赖，Facet 之间不建立边。Workflow 版本根据这些源图派生固定的 Combination Facet，其中包含真正执行的 Combination Node DAG。

```text
Workflow Version
├── Source Facet
│   └── Facet Node DAG
├── Source Facet
│   └── Facet Node DAG
└── Combination Facet
    └── Combination Node DAG
```

例如：

```text
Feature: start → Login → end
         start → Notification → end

Layer:   start → Domain → Application → Presentation → end
```

会形成两条可以并行的执行链：

```text
Login × Domain → Login × Application → Login × Presentation

Notification × Domain → Notification × Application → Notification × Presentation
```

执行顺序由 Combination Node DAG 决定。Workflow Runtime 找到前置依赖已满足的节点，在并发限制内启动 Combination Worker；Runtime 负责调度和监督，Worker 负责实际运行 Agent、命令、测试、Git 检查点和 Gate。

## 核心概念

| 概念 | 含义 |
| --- | --- |
| **Requirement** | 一次开发目标，通常绑定独立 Git Branch 和 Worktree |
| **Workflow** | Source Facet、Facet Node DAG 和 Combination Facet 的版本化定义 |
| **Source Facet** | 一个需求拆分维度，例如 Feature、Layer 或 Quality |
| **Facet Node** | Source Facet 中只提供上下文的节点，不单独执行 |
| **Combination Facet** | 多个 Source Facet 派生出的执行 Facet，在 Workflow 版本内固定 |
| **Combination Node** | 从每个 Source Facet 选择一个 Facet Node 后形成的业务执行单元 |
| **Combination Worker** | Runtime 启动的进程或容器，负责一次 Combination Node 执行 |
| **Gate** | 对执行成果进行需求对齐、验收或授权的关卡 |

## 执行闭环

```text
Requirement
    ↓
Git Branch + Worktree
    ↓
Combination Facet / Combination Node DAG
    ↓
Workflow Runtime 找到 ready Combination Node
    ↓
启动 Combination Worker
    ↓
Pre-Assess → Agent / Tool → Artifact → Git Commit → Post-Assess → Gate
    ↓
后继节点就绪，或根据 Gate 结果回到上游修复
    ↓
集成验证 → Squash Merge → main
```

Facet Node 只提供上下文，Combination Node 才真正执行。没有依赖路径的 Combination Node 可以并行。Gate、Commit 和运行记录都绑定具体的 Workflow 版本、Combination Node 和 Git 内容快照。

## 当前范围

首版先验证一个 Requirement 的完整闭环：

- 两个 Source Facet，各自包含少量 Node DAG；
- 固定生成 Combination Facet 和 Combination Node DAG；
- Runtime 调度就绪节点，并允许无依赖分支并行；
- Worker 在隔离 Worktree 和 Rootless Podman 环境中执行；
- Git Manager 创建组合级 Commit，SQLite 保存运行、Gate 和 Git 引用；
- WebUI 展示 DAG、Diff、日志、Gate 接管和执行历史。

首个适合验证的场景是跨多个架构层的功能需求，例如“登录失败五次后暂时限制登录，并在界面显示剩余等待时间”。

适用性规则、Combination Node 状态、并行 Worktree 合并、Gate 回退影响范围和多用户运行状态仍在设计中，以 [idea.md](./idea.md) 中的待确认事项为准。

## 文档

- [总体架构与设计共识](./idea.md)：当前唯一的系统设计基准。

当前项目处于想法和架构收敛阶段。安装方式、运行步骤和配置格式将在 Design 阶段确定。

## 研发路线图

### 阶段一：完善 idea

确定领域模型和职责边界，不提前锁定实现细节：

- 明确 Source Facet、Facet Node DAG、Combination Facet 和 Combination Node DAG 的关系；
- 明确 Combination Node、Combination Node Run、Combination Attempt 和 Combination Worker 的区别；
- 明确 Workflow Runtime 只调度和监督 Worker；
- 记录并行分支、DAG 汇合、Gate 回退和 Git 检查点的基本原则；
- 单独列出尚未决定的状态语义、适用性规则、并行集成和上下文优先级。

阶段产物是 `idea.md`。完成标准是核心术语不重复，执行顺序由 Combination Node DAG 决定，既定设计和待确认事项明确分开。

### 阶段二：建立 design

将 `idea.md` 转换为可以直接实现的技术契约，定义：

- 数据结构、DAG 生成算法和校验规则；
- Runtime 的 ready 节点计算、并发启动、汇合等待和恢复协议；
- Combination Worker 的输入、事件、输出、日志和 Attempt 协议；
- Git、Podman、SQLite、Agent Adapter 和首版 WebUI 的边界。

阶段产物是 `design.md` 以及必要的协议和数据结构草案。完成标准是可以据此拆分代码任务，不需要重新解释核心领域术语或 Runtime 与 Worker 的职责。

### 阶段三：代码 Demo

实现一个可运行的垂直闭环：

1. 创建 Requirement 和 Git Worktree。
2. 读取两个 Source Facet DAG，生成固定的 Combination Facet 和 Combination Node DAG。
3. Runtime 为就绪节点启动 Worker，并支持并行分支。
4. Worker 执行受控命令或 Agent Adapter，输出日志和结构化结果。
5. Git Manager 创建 Combination Node Commit，SQLite 保存运行和 Gate 记录。
6. 提供最小 Gate，以及 WebUI 或 CLI 的 DAG、状态、Diff 和日志展示。

Demo 暂不追求完整多用户权限、复杂适用性推断、无限并行、所有模型供应商适配或生产级部署体验。完成标准是用一条真实跨层需求跑通 Requirement、Combination Node、Worker、Commit 到 Gate 的可追踪链路。

## 命名约定

| 项目 | 名称 |
| --- | --- |
| 项目名称 | FacetLoom |
| 中文名称 | 维织 |
| 仓库名称 | `facetloom` |
| CLI 名称 | `facetloom` |
| 本地配置目录 | `.facetloom/` |

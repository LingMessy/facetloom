# Demo：登录失败限制与运行精炼

本场景验证单 main 下的 Requirement、DAG 并行、Gate、交付和 Refinement。

## 输入与组合图

需求：连续登录失败五次后暂时限制登录，并显示剩余等待时间。

```text
Feature: start → login → end
         start → notification → end
Layer: domain → application ─┐
       domain → data ────────┴→ presentation
```

Workflow 按 `feature ▷ layer` 生成组合图，静态排除 notification × application：

```yaml
exclude:
  - feature: [notification]
    layer: [application]
integration:
  checks:
    - id: regression
      argv: [pytest, -q]
      timeout_seconds: 900
```

```mermaid
flowchart LR
    D[login × domain] --> A[login × application]
    D --> DB[login × data]
    A --> P[login × presentation]
    DB --> P
    N[notification × domain] --> ND[notification × data]
    ND --> NP[notification × presentation]
```

Feature 分支可并行；每个 Feature 的 application 与 data 在 domain 满足后并行，presentation 汇聚二者。排除 `notification × application` 后，`notification × domain → notification × data → notification × presentation` 仍可达，因此无需添加旁路边。只有删除节点后某个原有上下游关系不再可达时才补边，避免跳过保留节点。控制边界和其余规则见 [Workflow](01-workflow.md)。

Verification Facet 可增加节点级验证，其边只约束其余 Facet 选择相同的组合，不自动构成全局验证屏障。最后的整体检查由 integration.checks 执行。

## 从运行到交付

1. 人类审阅并在 main 发布 Requirement r1、current、Workflow 和 Facet。
2. Runtime 固定 source_commit，生成 DAG，先本地持久化，再发布初始精简档案。代码仍未变。
3. Runtime 为根节点创建 Attempt，先保存本地输入再启动 detached Worktree 与容器。各 Worker 独立执行。
4. Git Manager 保存 Checkpoint。进入 waiting_gate 前导出必要 bundle、保存测试证据，并把精简上下文与结果发布 main。
5. 人类 Gate 批准当前 Attempt；Decision 和关联状态同 Commit 发布成功，后继才可执行。
6. application 与 data 并行，presentation 汇聚输入。若 Gate 发现缺少锁定到期后的恢复行为，要求修复 domain，相关后继 stale；人类确认重试后重新执行。
7. 所有节点 satisfied，Run completed。summary 记录结果、返工原因和待改进问题；完成不等于已经交付。
8. 另一个 clone 此时发布自己的 Run 档案。main 头变化，但 project_tree 不变，当前运行仍可交付。
9. Git Manager 在最新 main 上构造代码候选，保留全部最新档案，运行最终检查；人类确认后提交代码，并追加 DeliveryRecord。

如果第 8 步发生的是正式代码或定义变化，交付要求新 Run；同步到 r2 时取消旧版未终态运行，旧成果不能交付。

## 从记录到改进

```text
运行返工记录：多次遗漏锁定到期后的恢复行为
    ↓ 人类与 Agent 核对
有效经验：domain 上下文应检查时间边界与恢复状态
    ↓ Agent 建议与 Diff
为 layer/domain 补充状态边界检查约束
    ↓ 人类采纳、校验 Facet 与组合 DAG
改进通过 + 同 Commit 清理已处理记录
    ↓
未解决的通知问题继续保留；原证据从 Git 历史读取
```

Run 已交付且无其它有效引用依赖时才可清理对应证据。验证失败、部分采纳或会话中断都不直接删除原记录。Commit 描述引用删除前的证据、验证结论及精炼 ID。

## 产物

```text
main
├── 项目代码、Requirement、Workflow、Facet
└── .facetloom/runs/<run-id>/
    ├── run.yaml / summary.md / dag.yaml
    ├── contexts/ / combinations/ / attempts/
    └── checkpoints/ / decisions/ / reports/ / deliveries/

本地 .runtime/
├── 活动状态、待发布操作和 detached Worktree
├── 完整日志
└── refinements/<id>/

持久 Artifact
└── 可恢复代码的 bundle、测试报告与大型证据
```

## 验收场景

| 场景 | 预期结果 |
| --- | --- |
| 无效 Facet、排除引用或图有环 | 创建 Run 前拒绝 |
| 相同定义、不同 clone | 稳定 Combination ID 和 DAG，不同 Run ID |
| 无依赖分支、汇聚 | 并行执行，汇聚等待全部前驱 |
| 排除中间 Combination | 添加跨被排除节点的旁路边，保留原有可达关系 |
| Runtime 重启、Worker 丢失 | 本地对账；无法恢复则 blocked，人工确认重试 |
| 不同 Run 同时推送 | 刷新后自动追加，互不覆盖 |
| 同一 Run 的过期 Gate | 摘要不匹配，重新审核 |
| 仅运行档案变化 | 输入不失效，交付保留新档案 |
| 正式输入变化或需求被取代 | 拒绝旧结果交付 |
| bundle 在另一 clone 导入 | 可恢复被引用的输入与输出对象 |
| 部分采纳、验证失败、来源变化 | 保留待处理记录，必要时重新确认 |
| 精炼清理或回退 | 历史可追溯，回退恢复记录，无悬空有效引用 |
| Worker 尝试写 main 或人类决策 | 固定工具与凭据边界拒绝 |

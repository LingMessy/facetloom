# 筛选与执行图

Workflow 先生成静态 source-dag，运行前按需求筛选并采用 dag。图采用后不再增删节点，重试与修复只改变运行状态。

## 节点替换积

每个 Facet 是带虚拟 `start/end` 的合法 DAG。按声明顺序计算节点替换积；`G ▷ H` 表示将 G 的每个实际节点替换为一份 H 的实际子图，消除 H 副本的虚拟边界，并按 H 的全部入口/出口接续 G 的依赖。仅保留最外层 `start/end`。形式定义、合法性和边构造见 [节点替换积规范](../dag/DAG_节点替换积_规范.md)。

例如 Feature 在外、Layer 在内。下图是排除之前的完整替换积：

~~~mermaid
flowchart LR
    FD[feature:login × layer:domain] --> FA[feature:login × layer:application]
    FD --> FB[feature:login × layer:data]
    FA --> FP[feature:login × layer:presentation]
    FB --> FP
    ND[feature:notification × layer:domain] --> NA[feature:notification × layer:application]
    ND --> NB[feature:notification × layer:data]
    NA --> NP[feature:notification × layer:presentation]
    NB --> NP
~~~

## Facet 顺序与验证位置

以下使用同一组定义，不配置排除规则；图中省略 start/end：

~~~text
feature:      login 与 notification 两个独立分支
verification: implement（实施）→ verify（验证）
~~~

`feature ▷ verification`：每个 Feature 内复制一条实施与验证链。login 的实施成果通过 Gate 后，其验证即可启动，无需等待 notification。

~~~mermaid
flowchart LR
    LI[login × implement] --> LV[login × verify]
    NI[notification × implement] --> NV[notification × verify]
~~~

`verification ▷ feature`：外层的实施和验证节点各替换为一份 Feature 子图。实施子图的全部出口连接验证子图的全部入口，因此每个验证节点都等待两个实施节点的成果通过 Gate，并汇聚它们的输出。

~~~mermaid
flowchart LR
    IL[implement × login] --> VL[verify × login]
    IL --> VN[verify × notification]
    IN[implement × notification] --> VL
    IN --> VN
~~~

该例的阶段屏障来自外层 `implement → verify` 依赖与节点替换积，Facet 名称没有特殊调度语义。Verification 也不自动具有只读权限，写入边界仍由 Scope 与 Runtime 策略决定。两种顺序均须完成最终 `integration.checks` 与人类交付确认；节点验证不替代整体验收。

## 排除规则

排除发生在完整 Combination DAG 生成之后。键是 Facet ID，值是该 Facet 的普通 Node ID 列表；规则匹配最终 Combination Node 的 `members` 来源映射。

~~~yaml
exclude:
  - feature: [notification]
    layer: [application]
~~~

一条规则中，不同 Facet 的条件为 AND，同一 Facet 列表为 OR；规则之间为 OR。未列出的 Facet 不限。空规则、空列表、未知 Facet、未知 Node 或控制节点 ID 都是配置错误。exclude 只改变静态 DAG；之后可按需求筛选生成执行图，节点运行时 Applicability 不再增删节点。

## 组合 DAG 的生成规则

生成与排除按以下顺序执行：

1. 校验 Facet DAG，并按 `facets` 顺序左折叠节点替换积；规范的组合分组为 `(((F1 ▷ F2) ▷ F3) ... ▷ Fn)`。
2. 每个业务节点保留完整 `members`，键为 Facet ID、值为该 Facet 的普通 Node ID。虚拟边界不进入 members。
3. 在完整 DAG 上按 `exclude` 匹配 members，收集全部被排除的实际节点。
4. 删除命中节点，保留未删除端点之间的原有边。依据删除前的完整图做关系桥接：对保留节点或边界 `u`、`v`，若存在 `u → … → v` 路径且至少有一个内部节点、所有内部节点都被删除，则补上 `u → v`。候选边统一去重，不根据逐步补边后的可达性决定是否添加。
5. 对整个结果做传递约简，包括最外层 start/end：若一条边的端点间另有长度至少为 2 的路径，则该边冗余。保持节点集合及全部可达关系，只留下必要的直接依赖。没有 exclude 时也执行约简。
6. 校验结果无环，剩余每个实际节点仍从 start 可达并可达 end。排除全部实际节点或产生无效图时 Workflow 校验失败。

DAG 的边表达依赖顺序。对固定节点集合，DAG 的传递约简结果唯一，因此最终边集不受节点、边或补边遍历顺序影响。约简只在完整替换积与排除桥接完成后执行，不改变节点替换积本身的定义。

桥接例：

~~~mermaid
flowchart LR
    S([start]) --> A[A]
    A --> X[X 被排除]
    X --> B[B 被排除]
    B --> D[D]
    D --> T([end])
~~~

删除 X、B 后补上 `A → D`。若另有保留路径 `A → C → D`，仍先补边，再由传递约简删除冗余的 `A → D`：

~~~text
桥接后：A → C → D，另有 A → D
约简后：A → C → D
~~~

在全部前驱满足才执行的语义下，冗余边不会让 D 跳过 C；约简使图与直接前驱集合统一、精简。

Combination ID 使用 Workflow ID 和按声明顺序排列的 `members` 稳定编码，例如：

~~~text
development/feature:login/layer:domain
~~~

调度和代码输入汇聚统一使用筛选后实际执行 DAG 中的直接前驱。只有所有业务直接前驱的 CombinationRun 都为 satisfied，节点才可运行。互不依赖的就绪分支可并行；汇聚节点等待全部直接前驱。

## 运行前适用性筛选

筛选单位是静态组合图中的业务 Combination，不是原始 Facet Node。它判断当前需求是否需要该组合承担职责；节点 Pre-Assess 则在前驱完成后判断真实输入与适用性，两者均保留。

| mode | 输入与执行方式 | 主要取舍 |
| --- | --- | --- |
| global | 一个独立 Agent 会话读取完整组合图、需求与有效上下文 | 能统一比较职责，图大时上下文压力较高 |
| parallel | 每个组合一个独立会话，使用公共前缀、当前组合上下文和必要依赖摘要 | 分离关注点、可并发；不默认复制其他节点的全部资料 |

```text
节点替换积 → 静态 exclude → source-dag.yaml
    ↓ global / parallel 筛选
每组合 keep / exclude / defer
    ↓ automatic / human 采用
统一排除集合 → 旁路补边 → 传递约简 → 固定 dag.yaml
    ↓
前驱完成 → 节点 Pre-Assess → 执行、检查与 Gate
```

- keep 保留，exclude 提议排除，defer 表示当前材料不足以确定并保留。每项须有非空理由和依据；exclude 必须引用具体需求或职责材料。前驱尚未产出代码、基线缺少文件或无需改代码，不单独构成排除理由；验证职责同样参与判断。
- 筛选器不改节点、边、Scope 或配置，只报告业务节点判断。Runtime 以 source-dag 为裁剪前完整图，一次性计算最终排除集合；沿用 [组合 DAG 的生成规则](#组合-dag-的生成规则) 的旁路补边、传递约简和稳定序列化，忽略分项返回先后顺序。
- 被排除节点不创建 CombinationRun / Attempt，不运行其检查、Post-Assess 或成果 Gate。保留节点的职责、Scope、检查及 Gate 不变，代码输入来自执行图中的有效直接前驱；新根节点使用 source_commit。
- automatic 在报告与图校验通过后直接采用；human 等待一次集中确认，人类可恢复 exclude 节点或保留完整图，不能额外排除 keep / defer 节点或直接编辑边。筛选报告本身不被人工改写。
- 全部业务节点被提议排除时，无论 confirmation 如何配置都暂停。人类至少恢复一个节点后确认，或显式重试筛选、停止 Run；不生成空执行图，不把需求直接判定为满足。静态 exclude 排除全部节点仍是配置错误。
- 工作区草稿可暂缺 selection.mode / confirmation，显示不可运行；发布和启动要求完整有效配置。静态预览不发起 Agent 调用，需求相关筛选只在 Run 中执行。

采用前不调度业务节点；采用后执行图固定，筛选错误需在新 Run 中重新评估。节点 Pre-Assess 返回 not_applicable 时仍沿用已有检查与审核规则，不再次裁剪。筛选报告、采用记录及任务恢复见 [运行前筛选协议](#运行前筛选协议)。

## 运行快照

静态组合图与实际执行图使用相同格式。创建 Run 时先保存 source-dag.yaml；筛选采用后才保存 dag.yaml，执行期间不得改写。两者先在本地运行目录持久化，最终采纳时作为精简档案写入 main：

~~~text
.facetloom/runs/<run-id>/source-dag.yaml  # 节点替换积、静态 exclude 与约简后的图
.facetloom/runs/<run-id>/dag.yaml         # 采用筛选结果后的执行图
~~~

下面用只有 `login`、`domain` 和 `application` 的小图说明文件格式。

~~~yaml
schema_version: 1
workflow_id: development
nodes:
  - id: start
    role: start
  - id: development/feature:login/layer:domain
    role: regular
    members:
      feature: login
      layer: domain
  - id: development/feature:login/layer:application
    role: regular
    members:
      feature: login
      layer: application
  - id: end
    role: end
edges:
  - {from: start, to: development/feature:login/layer:domain}
  - {from: development/feature:login/layer:domain, to: development/feature:login/layer:application}
  - {from: development/feature:login/layer:application, to: end}
~~~

每个业务节点的 `members` 必须列出 Workflow 中每个 Facet 的 Node ID，顺序遵循 `facets` 声明顺序，并与 Combination ID 一致；控制节点不含 `members`。传递约简后，按 Combination ID 排列业务节点、按 `(from, to)` 排列边，再以固定字段顺序、UTF-8 和 LF 写出 YAML。`dag_digest` 对实际写入的完整文件字节求 SHA-256。相同定义生成相同 source-dag；相同 source-dag 与最终排除集合生成相同执行图。AI 筛选结论本身不保证跨次相同。采用后的 dag.yaml 不因重启、重试或节点修复改变。

## 运行前筛选协议

运行前筛选独立于 Attempt；模式、裁剪与确认规则见 [运行前适用性筛选](#运行前适用性筛选)。Run 创建时固定需求、source_commit、source-dag 和 selection。selection.instruction 是按当前筛选协议生成并保存的完整指令，后续重试不重新生成；policy_digest 对其余 selection 字段按 JCS 求 SHA-256，runner 完整配置由 Run.runners 提供。

```text
Run pending → selecting：保存轮次、任务身份和实际输入 → Agent 筛选
    ├── 报告 error → blocked → 错误 Gate：retry_selection / stop_run
    └── 报告 completed
          ├── 全部 exclude → blocked：人工恢复节点 / 重筛 / 停止
          ├── confirmation=human → blocked：一次集中确认
          └── confirmation=automatic → 校验并采用
                                  ↓
               selection_adoption + dag.yaml + running 同事务落地
```

### SelectionReport

路径为 `reports/<report-id>.yaml`，schema_version=1、report_type=selection，创建后不可变。每轮一个汇总报告，分项原始输出通过 Invocation Artifact 留存，不新增节点运行对象。

| 字段 | 定义 |
| --- | --- |
| report_id、run_id、selection_round_id | UUIDv4；轮次在调用前分配，重试使用新轮次与报告 ID |
| source_commit、requirement_ref、source_dag_digest、selection_policy_digest | 固定输入与策略；必须匹配当前 Run |
| mode、status | global / parallel；completed / error，成功不等于已采用 |
| results | 按 Combination ID 排序的 `{combination_id, decision, rationale, evidence_refs}` 列表 |
| invocation_refs | 本轮调用回执的 Artifact 引用；包含实际输入、原生结果与可观测程序信息 |
| reason、created_at | error 时非空原因，UTC 时间 |

completed 必须恰好覆盖 source-dag 的全部业务节点，decision 仅 keep / exclude / defer，rationale 非空。所有引用须来自提供的材料或统一导入的新证据；exclude 至少引用一项具体需求或职责依据。控制节点、未知/重复 ID、缺项或非法引用均为协议错误，不静默补成 defer。error 报告不作为裁剪依据，results=[]，有效分项与失败原文仍可通过 invocation_refs 查看。

Agent 输出示例；global 返回完整列表，parallel 每次只返回当前组合一项：

```json
{
  "schema_version": 1,
  "results": [
    {
      "combination_id": "development/feature:login/layer:domain",
      "decision": "keep",
      "rationale": "需求包含连续失败阈值和限制期，需由领域组合实现。",
      "evidence_refs": []
    }
  ],
  "evidence_files": []
}
```

evidence_files 使用统一导入协议，其规范化引用保存在调用回执中；results 中的 evidence_refs 只能使用请求明确提供的类型化引用，不能自行构造新引用。exclude 必须依据已提供的需求或职责资料，新增附件不能代替该依据。Runtime 保存完整实际输入，不能用后来重新生成的提示替代原请求。

### 采用记录

Run.selection_adoption 初始为 null；采用时设置一次，之后不改写。它是运行记录中的固定字段组，不是成果 GateDecision。

| 字段 | 定义 |
| --- | --- |
| report_ref | 当前 completed SelectionReport 类型化引用，等于 Run.selection_report_ref |
| mode | automatic / human；全部排除后恢复节点必须为 human |
| excluded_ids | 最终排除的 Combination ID，去重后升序排列，只能是报告 exclude 集合的子集 |
| dag_digest | 实际执行图的字节摘要，等于 Run.dag_digest |
| input_digest | 对 `{report_ref, excluded_ids, dag_digest}` 的 JCS SHA-256；报告已绑定需求、源图与策略 |
| adopted_by、adopted_at | automatic 为 Runtime 身份，human 为受信用户身份；UTC 时间 |

确认请求携带 input_digest；服务重新构造候选图和摘要，不信任前端传入的边。automatic 必须使用全部建议排除集合；human 仅在配置要求人工确认或全部排除暂停时采用，可恢复节点，excluded_ids=[] 表示保留完整 source-dag。最终业务节点数必须大于零。新报告、不同恢复节点集合或候选图变化使旧确认失效，报告本身不被修改。

采用事务复核活动轮次、Run 状态、source_commit 的正式输入及需求未采纳，原子保存采用记录、执行图、摘要和 running 状态。重复确认返回既有采用结果；不同确认不能覆盖它。所有筛选证据、原图与采用记录纳入既有归档、交换包与清理保护；被排除节点的依据不能因没有 Attempt 而遗漏。

### 调度与失败恢复

每轮在本地操作日志保存 selection_round_id、report_id、全体任务 ID、固定输入摘要及进度；global 一个任务，parallel 按 source-dag 的 Combination ID 分配一个任务。发起调用前先持久化身份和实际输入。各调用使用独立只读容器及新会话，不创建 Attempt / Worker，不挂载可写项目或 Git 管理凭据。

公共前缀按固定顺序放筛选规则、冻结需求和必要项目背景，组合专属上下文置后；parallel 提供完整拓扑的精简职责摘要以定位依赖，不复制其他组合的全部资料。资料均从固定基线解析，不以缺少未来前驱输出为调用错误；无法判断应返回 defer。外部 Agent 的内部提示和缓存策略由其实现决定，不保证 KV 命中。

只有本轮所有分项成功且覆盖完整才发布 completed 报告，不将部分 exclude 提前应用。调用超时、原生失败、无效结构、缺项或证据导入错误使本轮失败；先撤销其余任务并停止或隔离，再保存 error 报告、scope=selection 的 ErrorRecord 与 Run.blocked，交 Workflow 错误 Gate。本地持久化失败先恢复事务，不以半份报告推进。

retry_selection 只在执行图尚未采用、固定输入有效、旧调用已停止或隔离时有效：清空当前筛选报告及 Run 级错误引用，以新轮次完整重筛，不拼接不同轮次分项。AI/脚本重试消耗 Run 自动恢复额度，人类重试不消耗；所有历史报告保留。全部 exclude 是 completed 报告，记录 selection_empty 并等候人工，不创建 ErrorRecord 或自动重试循环；人类可显式重筛、恢复至少一个节点后确认或停止。普通 human 待确认也允许人类显式重筛或停止。完整报告后的人工重筛属于采用前操作，保存操作者、原报告与新轮次的本地操作意图，不伪造错误决定、不消耗自动恢复额度。

取消、显式重筛或基线变化先持久化撤销，迟到输出不得进入当前报告或采用记录。重启重放事务后按 Invocation 身份对账，不重复发起未知调用；重试与确认共用 Run 锁。采用后不再接受筛选重试，若需恢复已排除节点或切换筛选配置则新建 Run。保留节点继续执行固有 Pre-Assess，完整检查和审核规则不变。

## 筛选调用协调

筛选任务使用 Invocation.owner `{kind: selection, id: <selection-round-id>}`、task_kind=select；global 一次调用，parallel 为每个组合分配独立 invocation_id。各调用从 Run.selection 取得固定 runner、指令和策略，使用只读 source_commit 与引用资料，不挂载可写项目或其它会话，也不需要 Worker / Attempt。

任务的固定输入、分项进度、取消与对账保存在现有本地操作日志；汇总对象与采用事务见 [运行前筛选协议](#运行前筛选协议)。parallel 按稳定 Combination ID 入队，受 clone 本地正整数 `selection_concurrency` 限制（默认 4），并遵守全局进程/资源上限；超限排队不算调用超时。每次调用按固定 runner.timeout_seconds 计时，重启不重置，不重用原生会话串联不同组合。

只有任务身份、轮次与输入摘要匹配的结果才能计入汇总；全部分项成功前不创建有效裁剪图。报告发布、人工确认和自动采用通过同一 Run 锁校验；重复采用返回既有结果。报告、图或恢复节点集合变动后拒绝旧确认，采用成功后拒绝后续重筛与覆盖。实际传入外部 Agent 的输入逐次保存；不根据是否命中模型缓存改变业务结论。

# Workflow 与 Combination DAG

Workflow 是执行图的生成规则。Facet 提供一个上下文维度；Node 是该维度中的上下文节点；Combination 才是实际执行单元。

## 对象关系

~~~mermaid
flowchart TB
    WF[Workflow] --> F1[Facet: feature]
    WF --> F2[Facet: layer]
    F1 --> N1[Node]
    F2 --> N2[Node]
    N1 --> P[组合候选]
    N2 --> P
    P --> X[静态过滤]
    X --> DAG[Combination DAG]
    DAG --> CR[CombinationRun]
~~~

| 对象 | 说明 | 是否执行 |
| --- | --- | --- |
| Workflow | Facet 引用、排除规则、执行策略、Gate 策略 | 否 |
| Facet | 一个上下文维度及其内部 DAG | 否 |
| Node | Facet 中的上下文节点 | 否 |
| Combination | 由有序 Facet 组合生成、带 Facet→Node 来源向量的实际节点 | 是 |
| start / end | 图的控制节点 | 否 |

Facet 之间不直接连边。Workflow 按 `facets` 声明顺序，对每个 Facet DAG 连续应用节点替换积，生成更大的 Combination DAG。Facet 顺序是图语义的一部分：替换积不满足交换律，调换 Facet 顺序可能改变依赖拓扑。

## 文件布局

~~~text
.facetloom/
├── workflows/<workflow-id>.yaml
├── facets/<facet-id>/facet.yaml
├── facets/<facet-id>/scopes.yaml          # 可选
├── evaluators/<evaluator-id>.yaml         # AI / 脚本审核配置
└── references/...                         # 被 Facet 或 Requirement 引用
~~~

定义文件及引用资料由 WorkflowRun 的 `source_commit` 固定。`.facetloom/runs/` 是输出档案，不得用作定义或资料输入。定义修改供新 Run 使用；交付前须验证当前输入仍匹配运行基线。

## Workflow 文件

路径：.facetloom/workflows/<workflow-id>.yaml

~~~yaml
schema_version: 1
id: development
name: Software Development
facets:
  - ref: ../facets/feature/facet.yaml
  - ref: ../facets/layer/facet.yaml
exclude:
  - feature: [notification]
    layer: [application]
execution:
  agent: codex
  checkpoint: git-commit
gate:
  mode: human
integration:
  checks:
    - id: regression
      argv: [pytest, -q]
      timeout_seconds: 900
~~~

| 字段 | 必填 | 定义 |
| --- | --- | --- |
| schema_version | 是 | 文件格式，当前为 1 |
| id | 是 | 稳定 Workflow ID；路径文件名必须匹配 |
| name | 否 | 展示名称 |
| facets | 是 | 按稳定顺序排列的 Facet 引用，至少一个 |
| exclude | 否 | 静态排除规则，默认空列表 |
| execution | 否 | Agent 与检查点策略；并发配置见 Services |
| gate | 否 | 每个普通 Node 继承的默认 Gate 策略 |
| integration | 否 | 交付前运行的最终检查；格式见下文 |

Facet 列表顺序定义从外到内的替换顺序：`F1 ▷ F2 ▷ ... ▷ Fn`。不是节点执行顺序。替换积结合，因此多 Facet 的分组不影响结果；但不能交换 Facet 顺序。至少一个 Facet；同一 Workflow 不得重复引用同一 Facet ID。

| 嵌套字段 | 默认值 | 定义 |
| --- | --- | --- |
| execution.agent | Runtime 配置 | Agent Adapter ID |
| execution.checkpoint | git-commit | 当前只支持此值；代码输出以 Git Commit 保存 |
| gate.mode | human | `human`、`ai_assisted`、`ai` 或 `script` |
| gate.evaluator | 无 | source_commit 中的 AI / 脚本评估器 ID；自动评估必须提供匹配类型的配置 |
| gate.context | 空 | 审核目标、约束与资料；与 Node 的审核上下文累积 |

`integration.checks` 是非空有序检查列表，每项含 Workflow 内唯一的稳定 `id`、非空参数数组 `argv` 和正整数 `timeout_seconds`。命令按参数数组执行，不经 Shell 展开。`integration` 可省略；省略时 WorkflowRun 仍可完成，但不能生成通过的 IntegrationReport 或交付成果。

并发上限属于每个 clone 的 Runtime 配置，不属于 Workflow 语义。

### Node Gate 与组合审核

每个选中 Node 为 Combination 贡献一项 Gate，标识为 `facet_id/node_id`。`mode` 和 `evaluator` 分别按 Node → Workflow 解析；模式最终缺省为 `human`。Node 未声明 `gate` 时完整继承默认配置。有效模式为 `human` 时不调用评估器，快照中的 evaluator 为 null；其他模式缺少评估器或类型不匹配时校验失败。

Workflow 与 Node 的 `gate.context` 使用 `objective`、`constraints`、`references`，字段格式同任务 context。目标与约束累积，资料去重并保留声明来源；不按 Node 顺序覆盖，冲突时阻塞。资料路径相对各自声明文件解析，再固定到 source_commit。

~~~text
Combination: feature:login × layer:domain
├── feature/login：继承 Workflow 的 human
└── layer/domain：Node 指定 ai + domain-reviewer
                       ↓
                 两项都批准才接受成果
~~~

各 Gate 审核同一 Attempt 的固定输出，可并行执行；相同模式也分别记录，不按 Facet 顺序执行，不额外增加 Workflow 总审核。Gate 是 Combination 的审核项，不形成 DAG 业务节点，也不让原始 Node 独立执行。决策与异常处理见 [Governance](03-governance.md)。

### 排除规则

键是 Facet ID，值是该 Facet 的普通 Node ID 列表。规则匹配最终 Combination 的 `members` 来源映射。

~~~yaml
exclude:
  - feature: [notification]
    layer: [application]
~~~

一条规则中，不同 Facet 的条件为 AND，同一 Facet 列表为 OR；规则之间为 OR。未列出的 Facet 不限。空规则、空列表、未知 Facet、未知 Node 或控制节点 ID 都是配置错误。匹配规则是静态定义校验的一部分；运行时 Applicability 不增删 DAG 节点。

## Facet 与 Node

Facet 路径：.facetloom/facets/<facet-id>/facet.yaml

~~~yaml
schema_version: 1
id: layer
name: Architecture Layer
scope:
  mapping: scopes.yaml
context:
  references:
    - ../../references/common.md
nodes:
  - id: start
    role: start
  - id: domain
    role: regular
    scope: auth
    context:
      objective: 维护领域模型及业务规则
      references:
        - ../../references/domain.md
      constraints:
        - 不依赖具体基础设施实现
    gate:
      mode: ai
      evaluator: domain-reviewer
      context:
        objective: 审核领域模型及业务边界
        references:
          - ../../references/domain-review.md
  - id: application
    role: regular
    context:
      objective: 维护用例与应用服务
  - id: data
    role: regular
    context:
      objective: 维护仓储实现与数据访问
  - id: presentation
    role: regular
    context:
      objective: 集成应用服务和数据访问结果
  - id: end
    role: end
edges:
  - {from: start, to: domain}
  - {from: domain, to: application}
  - {from: domain, to: data}
  - {from: application, to: presentation}
  - {from: data, to: presentation}
  - {from: presentation, to: end}
~~~

| 字段 | 必填 | 约束 |
| --- | --- | --- |
| Facet schema_version | 是 | 当前为 1 |
| Facet id | 是 | 稳定 ID；在同一 Workflow 中唯一 |
| Facet name | 否 | 展示名称 |
| Facet scope.mapping | 否 | 相对 Facet 文件的 Scope 映射文件路径 |
| Facet context | 否 | 所有普通 Node 共享的上下文；字段与 Node context 相同 |
| Facet nodes | 是 | 有序 Node 列表，恰有一个 start、一个 end 和至少一个普通 Node |
| Facet edges | 是 | 本 Facet 内的有向边 |
| Node id | 是 | 所属 Facet 内稳定且唯一 |
| Node role | 是 | start、regular 或 end |
| Node name | 否 | 展示名称 |
| Node scope | 否 | scopes.yaml 中的 Scope ID |
| Node context | 否 | 普通 Node 的目标、约束和资料引用 |
| Node gate | 否 | 当前 Node 的审核模式、评估器与审核上下文；未声明字段继承 Workflow |

Facet 和普通 Node 的 `context` 都是可选的，可包含 `objective`、`references` 和 `constraints`。`objective` 可省略，填写时必须是非空文本；Facet 的目标说明其共享上下文，Node 的目标说明该 Combination 的工作边界。`references` 是相对声明文件的资料路径列表，默认空；`constraints` 是约束文本列表，默认空。`start` / `end` 不得声明 `scope`、`context` 或 `gate`。

Scope 示例文件 scopes.yaml：

~~~yaml
schema_version: 1
mappings:
  - scope_id: auth
    paths: [src/auth/**, test/auth/**]
  - scope_id: shared
    paths: [src/shared/**]
~~~

scope.mapping 是相对 Facet 文件解析的路径。每个 scope_id 在该文件中唯一，Node 的 scope 必须能解析到一个 mapping。paths 是仓库相对 POSIX glob；禁止绝对路径、空路径和包含 .. 的路径。未声明 Scope 的 Node 没有额外路径范围。

Node 列表顺序只用于稳定表示，不是依赖。每张 Facet DAG 必须满足：

- start 无入边，end 无出边；
- 所有普通 Node 都位于 start 到 end 的路径上；
- 图无环，无自环、重复边或悬空端点。

Scope 用于解释某个 Node 可关联的项目路径，不会自行授予文件访问权。实际访问由 Runtime 的文件、工具和容器配置限制。

Workflow 的 Facet 引用相对 Workflow 文件解析；Facet 和 Node 的资料引用相对 Facet 文件解析。路径经规范化并解析符号链接后不得越出仓库。Workflow、Facet、Node 和 Scope 的 ID 使用 `[A-Za-z0-9][A-Za-z0-9_-]*`，避免与路径、Combination ID 分隔符混淆。

## 执行上下文

Context Snapshot 由以下来源合成：

~~~mermaid
flowchart LR
    R[Requirement] --> C[Context Snapshot]
    W[Workflow] --> C
    F[Facet shared context] --> C
    N[Selected Node context + Scope] --> C
    P[Accepted predecessor outputs] --> C
    G[各 Node 的有效 Gate 策略与审核上下文] --> C
~~~

引用资料保留来源并按内容去重；目标和约束累积，不按列表顺序覆盖。约束冲突时阻塞并请求评估。一个 Scope 内的路径取并集，各选中 Node 的 Scope 之间取交集；未声明 Scope 不增加限制。最终读写范围还须与 Runtime 配置允许的路径取交集。

Snapshot 保存有效输入清单，Adapter 实际发送的初始上下文另通过 Attempt.agent_input_ref 留存，规则见 [Execution](04-execution.md)。执行、必要测试和 Post-Assess 完成后冻结审核输入，再启动各项 Gate。

动态 Applicability 和 Pre-Assess 在 Attempt 中执行，不改变组合 DAG。Applicability 明确为不适用时，Attempt 必须保存理由和证据；无法判断时阻塞，不能默认跳过 Workflow 要求的验证。

## 组合 DAG 的生成规则

每个 Facet 是带虚拟 `start/end` 的合法 DAG。按声明顺序计算节点替换积；`G ▷ H` 表示将 G 的每个实际节点替换为一份 H 的实际子图，消除 H 副本的虚拟边界，并按 H 的全部入口/出口接续 G 的依赖。仅保留最外层 `start/end`。形式定义、合法性和边构造见 [节点替换积规范](dag/DAG_节点替换积_规范.md)。

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

生成与排除按以下顺序执行：

1. 校验 Facet DAG，并按 `facets` 顺序左折叠节点替换积；规范的组合分组为 `(((F1 ▷ F2) ▷ F3) ... ▷ Fn)`。
2. 每个业务节点保留完整 `members`，键为 Facet ID、值为该 Facet 的普通 Node ID。虚拟边界不进入 members。
3. 在完整 DAG 上按 `exclude` 匹配 members，收集全部被排除的实际节点。
4. 删除命中节点，并做关系桥接：对保留节点或边界 `u`、`v`，若原图有一条 `u → … → v` 路径且所有内部节点都被删除，并且删除后当前图中已不存在 `u` 到 `v` 的路径，则添加 `u → v`。其他保留路径仍可达时不添加捷径；重复边合并。
5. 校验剩余每个实际节点仍从最外层 start 可达并可达 end，且结果无环。排除全部实际节点或产生无效图时 Workflow 校验失败。

桥接例：

~~~mermaid
flowchart LR
    S([start]) --> A[A]
    A --> X[X 被排除]
    X --> B[B 被排除]
    B --> D[D]
    D --> T([end])
~~~

删除 X、B 后，`A` 与 `D` 失去可达路径，因此添加 `A → D`。若另有保留路径 `A → C → D`，则不添加这条旁路，避免跳过保留节点。

Combination ID 使用 Workflow ID 和按声明顺序排列的 `members` 稳定编码，例如：

~~~text
development/feature:login/layer:domain
~~~

只有所有直接前驱的 CombinationRun 都为 satisfied，节点才可运行。互不依赖的就绪分支可并行；汇聚节点等待全部直接前驱。

## 运行快照

生成后的完整图先在本地持久化，再作为精简运行档案发布到 main：

~~~text
.facetloom/runs/<run-id>/dag.yaml
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

每个业务节点的 `members` 必须列出 Workflow 中每个 Facet 的 Node ID，顺序遵循 `facets` 声明顺序，并与 Combination ID 一致；控制节点不含 `members`。先按 Combination ID 排列业务节点、按 `(from, to)` 排列边并去重，再以固定字段顺序、UTF-8 和 LF 写出 YAML。`dag_digest` 对实际写入的完整文件字节求 SHA-256。相同定义必须生成相同 DAG；后续定义变化、重启和重试都不能改写该快照。

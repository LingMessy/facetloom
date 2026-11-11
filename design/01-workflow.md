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
├── runners/<runner-id>.yaml               # 外部 Agent 调用配置
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
  runner: developer
  checkpoint: git-commit
  checks:
    - id: unit
      argv: [pytest, -q]
      timeout_seconds: 900
  max_check_retries: 2
gate:
  mode: human
error_gate:
  mode: human
  max_auto_recoveries: 3
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
| execution | 是 | 外部 Agent 调用配置、检查点、必要检查和修复预算；并发配置见 Services |
| gate | 否 | 每个普通 Node 继承的默认 Gate 策略 |
| error_gate | 否 | Workflow 唯一的错误处置策略，独立于各 Node 的成果 Gate |
| integration | 否 | 交付前运行的最终检查；格式见下文 |

Facet 列表顺序定义从外到内的替换顺序：`F1 ▷ F2 ▷ ... ▷ Fn`。不是节点执行顺序。替换积结合，因此多 Facet 的分组不影响结果；但不能交换 Facet 顺序。至少一个 Facet；同一 Workflow 不得重复引用同一 Facet ID。

| 嵌套字段 | 默认值 | 定义 |
| --- | --- | --- |
| execution.runner | 无，必填 | source_commit 中 runners/<id>.yaml 的调用配置 ID，不使用本地配置兜底 |
| execution.checkpoint | git-commit | 当前只支持此值；代码输出以 Git Commit 保存 |
| execution.checks | 空列表 | Workflow 必要检查；与选中 Node 的检查累积 |
| execution.check_environment | runner 镜像、network=disabled | 可显式配置 image_ref（digest）和 network（disabled / outbound），供必要检查及最终 integration.checks 使用 |
| execution.max_check_retries | 2 | 同一 Attempt 内修复并重检的最大次数，非负整数 |
| error_gate.mode | human | 四种模式之一；evaluator、context 的格式同 gate，不继承成果 gate |
| error_gate.max_auto_recoveries | 3 | 整个 Run 共享的自动恢复动作上限，非负整数 |
| gate.mode | human | `human`、`ai_assisted`、`ai` 或 `script` |
| gate.evaluator | 无 | source_commit 中的 AI / 脚本评估器 ID；自动评估必须提供匹配类型的配置 |
| gate.context | 空 | 审核目标、约束与资料；与 Node 的审核上下文累积 |

`integration.checks` 是非空有序检查列表，每项含 Workflow 内唯一的稳定 `id`、非空参数数组 `argv` 和正整数 `timeout_seconds`。命令按参数数组执行，不经 Shell 展开。`integration` 可省略；省略时 WorkflowRun 仍可完成，但不能生成通过的 IntegrationReport 或交付成果。

并发上限属于每个 clone 的 Runtime 配置，不属于 Workflow 语义。

### 外部 Agent 调用配置

FacetLoom 通过 Adapter 调用 Codex、Claude Code、OpenCode、Pi Agent 等外部程序。模型调用、工具循环、上下文压缩与原生会话由外部 Agent 完成；FacetLoom 负责图调度、任务输入、检查和 Gate。

路径：`.facetloom/runners/<runner-id>.yaml`。以下原生参数是占位符，实际文件须填写对应 Agent 版本支持的参数；不把不同程序的参数名混用。

~~~yaml
schema_version: 1
id: developer
adapter: claude_code
image_ref: registry.example.com/project-agent@sha256:<image-digest>
args: ["<native-non-interactive-arg>", "<native-bypass-approvals-arg>"]
config_refs: []
timeout_seconds: 1800
network: outbound
~~~

| 字段 | 规则 |
| --- | --- |
| schema_version、id | 格式为 1，ID 与文件名一致，格式同 Node ID |
| adapter | 外部 Agent 适配器 ID；接入目标为 codex、claude_code、opencode、pi_agent |
| image_ref | OCI 镜像的不可变 digest 引用，预装对应 Agent、依赖及项目运行环境 |
| args | 原生参数数组，可为空；按参数传递，不经 Shell 展开 |
| config_refs | 相对当前 runner 文件的原生配置文件路径列表，默认空；source_commit 固定内容 |
| timeout_seconds | 正整数，执行时限；1800 只是示例值，必须显式填写 |
| network | 必填，disabled 或 outbound；outbound 允许访问模型服务，仍受 Runtime 网络边界约束 |

可通过 args 或原生配置选择模型、工具、非交互模式，并按需要关闭外部 Agent 的审批和内部沙箱；FacetLoom 不定义通用的 model / parameters / tools Schema。Adapter 只负责映射调用协议，不能补充未记录的模型或权限参数。Runtime 网络策略不足以满足配置时明确报错，不静默更换调用方式。

原生配置文件只读提供给 Adapter 约定的配置位置，映射规则随 Adapter 版本记录；镜像内默认配置由 image_ref 固定。不挂载宿主机 Agent 配置或共享可写会话目录，本地仅注入必要凭据与连接；参数、配置和记录均不得含明文凭据。程序启动时禁止自动升级 Agent 或临时安装依赖。

Run 启动时解析执行与 AI 评估所引用的全部 runner，保存完整 profile、来源文件引用和 profile 的 JCS SHA-256 摘要。source_refs 包含 runner 文件及 config_refs 的全部原生配置文件，均固定到 source_commit 并校验内容摘要；profile_digest 不代替来源文件校验。后续 Attempt 与评估调用只引用这些固定配置；定义缺失或格式错误拒绝创建 Run，运行能力不足按执行错误或评估器故障分别处理。调用与取消协议见 [Services](05-services.md)。

### 必要检查

Workflow 的 `execution.checks` 提供默认检查，普通 Node 的 `execution.checks` 追加检查。每项含唯一 `id`、非空 `argv` 参数数组和正整数 `timeout_seconds`；ID 格式同 Node ID。允许省略或空列表。命令不经 Shell 展开。

~~~yaml
# Node 片段
id: domain
role: regular
execution:
  checks:
    - id: boundaries
      argv: [pytest, -q, test/auth/test_boundaries.py]
      timeout_seconds: 120
~~~

有效检查按 Workflow → facets 声明顺序 → 各列表顺序累积，不能覆盖或移除。限定 ID 为 `workflow/<id>` 或 `<facet>/<node>/<id>`，同一声明者内部不能重复。`execution.max_check_retries` 仅在 Workflow 配置。修复、全量重检和 CheckReport 对象见 [Execution](04-execution.md)。`integration.checks` 独立用于交付，不替代节点检查。

### 错误 Gate

每个 Workflow 只有一项错误 Gate，`gate_id = workflow/error`。它决定重试当前节点、修复祖先、等待或停止，不接受代码成果。省略 `error_gate` 时等同 `mode: human, max_auto_recoveries: 3`；其他模式要求匹配的 evaluator。审核上下文只取自身声明，不继承 Node Gate。

启动 Run 时校验并把完整有效错误策略固定到 run.yaml，因此尚未形成 Context Snapshot 时也能处置错误。错误策略、成果策略、检查及引用无效时拒绝创建 Run，不调用错误 Gate 修复定义。协议见 [Governance](03-governance.md)。

### Node Gate 与组合审核

每个选中 Node 为 Combination 贡献一项 Gate，标识为 `facet_id/node_id`。`mode` 和 `evaluator` 分别按 Node → Workflow 解析；模式最终缺省为 `human`。Node 未声明 `gate` 时完整继承默认配置。有效模式为 `human` 时不调用评估器，快照中的 evaluator 为 null；其他模式缺少评估器或类型不匹配时校验失败。

Workflow 与 Node 的 `gate.context` 使用 `objective`、`constraints`、`references`，字段格式同任务 context。目标与约束累积，资料去重并保留声明来源；不按 Node 顺序覆盖，运行准备时发现语义冲突则进入错误 Gate。资料路径相对各自声明文件解析，再固定到 source_commit。

~~~text
Combination: feature:login × layer:domain
├── feature/login：继承 Workflow 的 human
└── layer/domain：Node 指定 ai + domain-reviewer
                       ↓
                 两项都批准才接受成果
~~~

各 Gate 审核同一 Attempt 的固定输出，可并行执行；相同模式也分别记录，不按 Facet 顺序执行，不额外增加 Workflow 总审核。Gate 是 Combination 的审核项，不形成 DAG 业务节点，也不让原始 Node 独立执行。决策与异常处理见 [Governance](03-governance.md)。

每个 Combination 接收完整 Requirement，并结合所选 Node 的目标、约束与 Scope 确定当前职责。各 Gate 从自己的角度审核该职责内的成果；批准表示当前组合可以继续推进，不表示整个需求已经实现。后续节点负责的工作尚未完成，不单独构成当前组合的拒绝理由，但不能据此忽略当前职责、固定约束或必要检查。

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
| Node execution.checks | 否 | 追加必要检查；不允许覆盖 Workflow 的 runner、检查环境、检查点或重试预算 |
| Node gate | 否 | 当前 Node 的审核模式、评估器与审核上下文；未声明字段继承 Workflow |

Facet 和普通 Node 的 `context` 都是可选的，可包含 `objective`、`references` 和 `constraints`。`objective` 可省略，填写时必须是非空文本；Facet 的目标说明其共享上下文，Node 的目标说明该 Combination 的工作边界。`references` 是相对声明文件的资料路径列表，默认空；`constraints` 是约束文本列表，默认空。`start` / `end` 不得声明 `scope`、`context`、`execution` 或 `gate`。

Scope 示例文件 scopes.yaml：

~~~yaml
schema_version: 1
mappings:
  - scope_id: auth
    paths: [src/auth/**, test/auth/**]
  - scope_id: shared
    paths: [src/shared/**]
~~~

scope.mapping 是相对 Facet 文件解析的路径。每个 scope_id 在该文件中唯一，Node 的 scope 必须能解析到一个 mapping。paths 是仓库相对 POSIX glob：`*` 和 `?` 不跨 `/`，`**` 可跨目录，支持字符集合，不支持否定规则；禁止绝对路径、空路径和包含 .. 的路径。范围交集按每个实际路径同时满足各组匹配条件判断，不对 glob 字符串求交集；Snapshot 使用 execution.write_scope.all_of 保留原始分组和来源，格式见 Execution。未声明 Scope 的 Node 没有额外路径范围。

Node 列表顺序只用于稳定表示，不是依赖。每张 Facet DAG 必须满足：

- start 无入边，end 无出边；
- 所有普通 Node 都位于 start 到 end 的路径上；
- 图无环，无自环、重复边或悬空端点。

Scope 约束代码写入，不授予额外访问权。读取项目、依赖和资料受 Runtime 读取策略限制，不取各 Node Scope 的交集。

Workflow 的 Facet 引用相对 Workflow 文件解析；Facet 和 Node 的资料引用相对 Facet 文件解析。路径经规范化并解析符号链接后不得越出仓库。Workflow、Facet、Node 和 Scope 的 ID 使用 `[A-Za-z0-9][A-Za-z0-9_-]*`，避免与路径、Combination ID 分隔符混淆。

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

引用资料保留来源并按内容去重；目标和约束累积，不按列表顺序覆盖。约束冲突进入错误 Gate。一个 Scope 内的路径取并集，各选中 Node 的 Scope 之间取交集；未声明 Scope 不增加限制。有效写入范围再与 Runtime 写入策略取交集，读取范围单独由 Runtime 决定。

空交集表示只读，允许有证据的 no_change 或 not_applicable；需要修改则报错，不自动扩权。Runtime 校验新增、删除、文件模式、重命名两端和符号链接目标，禁止通过路径或链接越界。自动汇聚已接受前驱的变更不受当前节点 Scope 重新裁剪；Agent 对汇聚输入的新增修改仍受约束。冲突路径必须全部在有效写入范围内，否则进入错误 Gate；逐项解决清单和确定性 conflict_id 见 [Execution](04-execution.md)。

Snapshot 保存有效输入清单，Adapter 实际发送的预检上下文另通过 Attempt.agent_input_ref 留存。正式 Pre-Assess 使用独立只读调用；缺少输入进入错误 Gate，风险作为证据交给已配置的成果 Gate。适用性与后续执行结果按 [Execution](04-execution.md) 的结构化协议校验；必要测试和只读 Post-Assess 完成后冻结审核输入，再启动各项 Gate。

动态 Applicability 和 Pre-Assess 在 Attempt 中执行，不改变组合 DAG。明确不适用时跳过代码执行但仍完成必要检查、Post-Assess 和所有成果 Gate；无法判断时进入错误 Gate，不能默认跳过 Workflow 要求的验证。

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

调度和代码输入汇聚统一使用最终约简 DAG 中的直接前驱。只有所有业务直接前驱的 CombinationRun 都为 satisfied，节点才可运行。互不依赖的就绪分支可并行；汇聚节点等待全部直接前驱。

## 运行快照

完成排除、桥接和传递约简的最终图先在 `.facetloom/.runtime/runs/<run-id>/dag.yaml` 持久化；最终采纳时作为精简档案写入 main：

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

每个业务节点的 `members` 必须列出 Workflow 中每个 Facet 的 Node ID，顺序遵循 `facets` 声明顺序，并与 Combination ID 一致；控制节点不含 `members`。传递约简后，按 Combination ID 排列业务节点、按 `(from, to)` 排列边，再以固定字段顺序、UTF-8 和 LF 写出 YAML。`dag_digest` 对实际写入的完整文件字节求 SHA-256。相同定义必须生成相同 DAG；后续定义变化、重启和重试都不能改写该快照。

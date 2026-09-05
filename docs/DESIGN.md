# fullstack-bridge 设计文档

> AI Foundation 系列 · 前后端连通层（多端确定性核心）
> 状态：架构定稿（2026-09 评审收敛：units/edges 拓扑 + 统一 Click CLI + 底座 clone/baked + 内省面 + R1/A2 + U1 共享）。多单元组合（N≥2）治理/执行已落 main（2026-09-05，53 测试）；R4/A1 与第二组合见 §12。本仓唯一事实源——改代码前先过它；评审意见/变更先改本文再动代码。

## 1. 定位

把**多端底座**（N≥2）按 units/edges 组合成**前后端一体大目录**，并做组合契约的治理与对齐。底座只约束单端机制与写法；本仓约束**多端怎么对上**：注册组合（combos.yaml 真源）→ 逐单元生成 → 契约裁剪渲染 → 对齐/漂移检查。

**核心原则：确定性核心 + 治理，代壳消化。** 生成能力层（bridge-mcp-server）**纯 cli 消费**本仓生成面（`generate` / 内省 `list-combos`·`show-combo`），`check` 属治理链服务 CI——能力层 MCP **不消费、不暴露**（见 §10、§11.10）。

| 归属 | 形态 | 谁做 |
|---|---|---|
| **多端契约** | ① 前后端分离（前端可含 BFF，N≥2） | 本仓：combos.yaml 注册组合 + 契约治理 + 生成 + check |
| 单端直生成 | ② 纯前端全栈 ③ 纯后端 ④ 纯前端 ⑤ 纯命令行 ⑥ 其它单模板 | **不进本仓**——bridge-mcp-server `generate_single`（底座协议自述、零注册） |

多端与单端链路不同是**结构性正确**：多端背后有治理（组合、version 基线、契约），值得一个注册表 + 确定性核心代 server 消化；单端背后只有一个 git 地址，底座自述即可。**本仓不反向长单端逻辑**——单端能力（列表/生成）不进桥。

## 2. 设计由来（为什么多端要单独一个连通层）

- 单端模板只约束「一端怎么长」；多端交付的真正难点是**两端怎么对上**——数据模型/接口/会话语义要一致，否则各自生成完拼不起来。
- 契约先行、实现收敛：两端在生成链内就拿到同一份裁剪后的 `CONTRACT.md`，对照开发 → 接口漂移在构造上减少。
- 底座各自演进（params.json 两区自述），需要一层按 version 钉住「该组合已复核到的底座状态」，底座变了要能检出（漂移）——这就是治理面。
- 不在能力层 server 里实现多端：那是薄封装（给菜单/校验/确定性执行），组合治理与对齐是确定性核心的活，放桥里一份，任何壳都经 cli 复用。
- 演进史（Click 化、砍本地模式统一 clone/baked、内省面、U1 共享）见 git 提交与 ai-foundation-review 报告，不在此回放。

## 3. 架构分层：units/edges 拓扑 + combos.yaml 真源

```
┌─ 生成能力层（bridge-mcp-server，纯 cli 消费本仓生成面）────────┐
│   list_combos / get_combo_params / generate_multi（shell-out）  │
└───────────────┬───────────────────────────────────┬────────────┘
  生成面 cli（--json）                                │ check（治理链，服务 CI）
┌───────────────▼───────────────────────┐   ┌────────▼──────────────────┐
│ 生成/内省：generate · list-combos ·   │   │ check（bridge-gate 门槛 /  │
│   show-combo                          │   │   check-drift 漂移信号）    │
│ cli.py Click · 底座 clone/baked ·     │   │ 结构门 → 检查1 漂移 → 检查2 │
│ copier 逐单元 + answers 剔除合并 →    │   │   覆盖（combos.yaml 基线）   │
│   combos/<combo>/ 契约 → README       │   └───────────────────────────┘
└──────────────────┬────────────────────┘
                   │ clone + checkout version（~/.cache/fullstack-bridge/bases）
┌──────────────────▼───────────────────────────────────────────────┐
│ 底座（git 注册裸名，协议自述）  template/ + copier.yml + 根 params.json │
│   params: 派生+hash 校验 · selection: 策展（技术事实单一真源）      │
└──────────────────────────────────────────────────────────────────┘
```

### 3.1 combos.yaml（多端治理真源）

```yaml
bases:                                  # 底座 git 地址注册表（source 裸名 → URL）
  vite-react-spa-template: https://github.com/jianghua-developer/vite-react-spa-template.git
combos:
  python-react:                         # 组合名 = cli generate 子命令名
    units:                              # key = 生成目录名（frontend/ backend/ …）
      frontend:
        source: vite-react-spa-template # 底座注册裸名（只认注册组合，Q4）
        version: 535f3d2                # 该组合已复核/对齐到的底座版本（手动维护）
        app:   "前端应用"                # README 职责描述（units_desc 装配）
        stack: "Vite + React + TypeScript + …"   # README 技术栈（数据驱动）
      backend:
        source: python-fastapi-template
        version: 3bf48bb
    edges: [[frontend, backend]]        # 有序对 [consumer, provider]；provider 契约属主
    selection:                          # 只放**组合不可约**事实（可缺省；§8）
      suited_for: ["前后端分离一体交付…"]
      tradeoffs: ["…"]
```

- `bases`：source 裸名在此解析 git 地址。底座一律 clone 到缓存 + checkout `version`——无源码兄弟目录模式。
- `units`：≥2；key = 生成目录名 + project_name 后缀。
- `edges`：必填显式，有序对 [consumer, provider]，provider 为契约属主（同名共享参数以 provider 为准，§6）。
- `version`：**手动维护**，非自动更新——是 `check` 漂移基线，也是 `generate` 的 checkout 目标。
- 加新组合 = combos.yaml 加 units+edges + 新建 `combos/<组合>/` 契约模板，`cli.py`/`bridge/` **零改动**（选项由 params.json 数据驱动）。完整 SOP 见 [docs/base-onboarding.md](base-onboarding.md)。

### 3.2 形态约束（结构门，validate_combo）

- units ≥ 2（桥只管理多单元组合；单模板形态走能力层 generate_single）。
- edges 必填、端点 key 合法；source 必须在 bases 注册表。
- **链形**：edges 数 = units−1（系列目前只支持链式契约；星型/环型未来需放宽，见 §12）。
- combo 段 selection 结构校验（字段限 suited_for/tradeoffs、须字符串数组、未知字段拒绝——§8）。

## 4. 运行形态与底座获取

### 4.1 底座一律 clone/baked

- 底座 git 地址只在 combos.yaml `bases` 注册；运行时 clone 到 `~/.cache/fullstack-bridge/bases/<source>`（`bridge.combos.BASE_CACHE`，clone-bases.py 共享导入、不双写），按 units 钉的 `version` checkout（本地缺 sha → fetch origin 重试）。
- 读参分流：
  - **frozen（`dist/bridge` 可执行）**：params.json 走打包时烘焙的 `_MEIPASS/bases_params/<source>.json`（schema/help 零网络）；
  - **源码**：走缓存 clone 的钉 version `params.json`（生成前 `resolve_template` 已 checkout 对齐）。
- 生成读 `base/template/`（copier.yml 在子目录）；check 的 `git show <ref>:params.json` 靠全量 clone 历史。

### 4.2 统一 Click CLI（cli.py）

命令树：

```
bridge generate <combo> <project> [选项…]   # combo 为 generate 组动态子命令（惰性构建）
bridge check [--combo | --all | --base-repo --base-version]
bridge list-combos [--json]                  # 多端菜单：units/edges + 合并 selection
bridge show-combo <combo> [--json]           # 参数基线（原生/派生）+ 合并 selection
```

- **选项由各 unit 底座 params.json schema 数据驱动**：不解析 copier.yml、不手抄参数、无 `-D` 自由透传。choices 只列 enabled（disabled 不暴露）；bool/int 强类型。
- **惰性 generate 组**：仅在解析真正落到某 combo 时才构建其 schema（`get_command`）——顶层 `check` / `--help` 零触网；某 combo schema 构建失败只告警跳过，不拖死整 CLI。
- **内部注入、不暴露为用户选项**：`project_name`（= project basename + 各单元 `-<key>` 后缀）/ `project_title`。
- 依赖：`copier`（API `run_copy`，打包进单文件的前提）/ `click` / `pyyaml`；开发依赖 pytest / pyinstaller / ruff（uv 管理，非发布型，`package=false`）。

### 4.3 可执行分发

`bridge.spec`（PyInstaller onefile）把 `cli.py` + 桥自身数据（combos.yaml / combos / templates）+ 烘焙 `bases_params/` 打进单文件 `dist/bridge`。copier 作运行时依赖随包；`jinja2_ansible_filters` 显式 hiddenimport（静态分析漏包）。构建前须 `clone-bases.py --all --collect-params bases_params`（烘焙 = combos.yaml 钉 version 的 params.json，保证 frozen schema 与源码一致）。CI `build-executable` workflow：打 tag `v*` 自动打包 + 发 GitHub Release，`workflow_dispatch` 产 artifact。

## 5. 生成链（integrate/）

`cli.py generate <combo> <project>`（点同名子命令，R1 只校验目标 combo）：

1. **逐单元生成**（按声明序）：`resolve_template(source, version)` → clone 缓存 + checkout 钉 version → `copier.run_copy(base/template → <project>/<key>, data={project_name: f"{project}-{key}", project_title: project, **user_params}, defaults=True, unsafe=True)`。依赖安装走底座 `_tasks`（前端 pnpm / 后端 uv sync），`--skip-tasks` 跳过（测试用）。
2. **读 answers**：每单元生成后读 `<key>/.copier-answers.yml`（剔除 `_` 开头的元键）。
3. **剔除合并**：`merge_answers_by(answers, order, user_params, project_name)`。`order = merge_order(edges)` 展平 consumer→provider、中间单元去重——`dict.update` 按序后者赢 → **per-edge 属主**（provider 赢）、**用户显式参数最高**（python-react 单 edge ≡ 用户 > 后端 > 前端）。`project_name` 恒为原始项目名（覆盖各端后缀）。
4. **契约渲染**：`copier.run_copy(combos/<combo> → <project>/docs, data=merged)`——渲染数据是各单元**实际生效值**（含 copier 默认），默认漂移在构造上不存在。
5. **项目 README 渲染**：`templates/project-README → <project>`，`units_desc` 由 cli.py 从 combos.yaml `units.{key}.{app,stack}` 装配注入（数据驱动，不加组合不改 README 模板）。

### 5.1 契约模板约定（combos/<combo>/）

- `copier.yml`：**全必填零默认** + `_envops.undefined = jinja2.StrictUndefined`——渲染数据由生成链喂入，无默认可漂移。
- 条件用各单元共享的原生 copier 参数名（auth_mode / with_db / …），布尔条件直接 `{% if with_db %}`（copier 类型强转）。
- **可用派生参数**（`when:false` 由 copier 算，如 `child_apps` 由 `child_apps_raw` 输入）：`{% for child in child_apps %}` 枚举子应用。派生逻辑须与底座同步（后端改派生时此处要跟着改；检查链只做原生参数字面读取，派生值由 copier 计算）。
- `{% yield %}` 仅限文件名、正文禁用。

## 6. 参数契约面：数据驱动 schema 与共享参数（U1）

- **数据源**：各 unit 底座 params.json（v2 两区，`params` + `selection`）。`param_schema` 暴露全部 `derived:false` 原生参数（含派生输入如 `child_apps_raw`）；`derived:true` 纯派生值（child_apps）**不暴露**（§5.1 契约可引用，CLI/生成不可传）。
- **跨 unit 同名合并**：去重取 **provider 端** spec（provider 为契约属主，default/choices 以其为准）；consumer 同名不覆盖。跨端 default/enabled choices 不一致 → **显式告警**（提示底座默认漂移），不静默取一。
- **身份参数例外**：`project_name`/`project_title` 各端可有独立默认（非契约决策）——不做共享一致性校验、不 provider 覆盖。
- **U1 共享参数**：同名出现于 **≥2 units** 的原生参数 = **全链单一决策、单值广播**，schema 标 `shared: true`（程序化标注，A2）；agent 给一个值即广播全链，不逐端命名空间、不能也不需分端指定。需要逐端差异 → 那是该单元私有参数的事（底座自述，如 BFF `upstream_auth`），非拆共享参数（定案与边界见 bridge-mcp-server DESIGN §4.10）。

## 7. 内省面（能力层纯 cli 消费，`--json` machine 输出）

能力层（bridge-mcp-server `list_combos` / `get_combo_params`）**只经桥 cli 读**，不读 combos.yaml、不 clone 内省——菜单/参数/selection/生成全经 `cli.py --json`。

- **list-combos**：多端菜单。每行 = combo + `units`（key/source/version/app/stack）+ `edges` + 合并 selection（L1 候选集 / L2 地基）。
- **show-combo <combo>**：单组合详情，结构门（validate_combo，单目标、本地无网络）。`params` = 可提问原生参数（剔除 internal，与 generate 可接受面**同构**，内省不会给出 generate 拒绝的键）；`internal`（project_name/project_title，勿传）/ `derived`（只读勿传）分列；`shared: true` 透传。
- 顶层 `--help` / 未落 combo 时惰性零触网（§4.2）。

## 8. selection 单一真源与 combo 段纪律

**选择事实单一真源在底座** params.json `selection` 区（技术栈 suited_for/tradeoffs，策展、schema 校验、gen-params 轮转保留）。桥只消费与**叠加组合不可约事实**：

- `SELECTION_FIELDS = ("suited_for", "tradeoffs")`，单一真源在 fullstack-param-protocol SCHEMA.md（S3）——协议新增字段时此处须同步；底座策展容忍未知字段轮转，桥 merge 只并已知字段。
- **combo 段（combos.yaml `combos.<name>.selection`）只放组合不可约事实**（配对/契约治理价值，如「前后端分离一体交付、契约随生成对齐」；相对单端分别生成的代价）。凡能从 units 底座 selection 区解析到的技术事实**禁止在此重复写**（防双源漂移）。可缺省。
- **合并**：完整 selection = 各 unit 底座 selection **并集**（去重、保留声明序）+ combo 段叠后；全部为空 → 无 selection。
- **结构校验**：combo 段字段仅限 suited_for/tradeoffs、出现须字符串数组、**未知字段拒绝**（组合层策展严格，防拼错漂移）；底座侧未知字段只告警不拒绝（轮转容忍）。门在 `validate_combo`——check 入口整注册表（A2）、generate/show-combo 单目标（R1）共用。

## 9. 检查链（check，check/ 子包）

`bridge check [--combo | --all | --base-repo --base-version]`，退出码 1 = 有漂移/未对齐。**结构门在 check 入口**（A2）：`validate_all_combos` 整注册表暴露缺 edges/非链/未注册 source/坏 combo 段 selection，不再静默放行。

**检查 1 漂移**（`check/params.py`）：每 unit 对比 **pinned（combos.yaml version）** vs **当前底座状态**。当前状态参照：有信号 → `--base-version` 该 ref（check-drift workflow 派发载荷，读取失败 = 真实错误显式报错，不回退）；否则 → 底座远端默认分支 `origin/HEAD`（check 前 `fetch origin` 刷新，离线失败仅提示沿用本地 ref）；origin 无该 ref 才回退工作树并注明。diff = params 区变化：新增/移除参数、enabled choices 变化、原生参数默认值变化。

**检查 2 覆盖**（`check/coverage.py`，启发式扫描）：
- 子集：契约声明参数（`combos/<combo>/copier.yml` 非 `_` 键）⊆ 底座参数并集；
- 取值覆盖：底座 enabled choices 在 CONTRACT.md.jinja 是否被显式覆盖。hard = 启用取值未显式覆盖且无 else 兜底（渲染为空，真缺口 → 未对齐）；advisory = 经 else 兜底（ℹ️ 提示，人审，不建 issue）。只检查契约声明集内参数——声明集外的底座参数契约本就不覆盖，不判缺口。支持 `{% %}` / `[[ ]]` 两种 envops 标签。

归属：`generate`/`show-combo` 只校验**目标** combo（坏兄弟不阻断健康目标，R1）；整注册表结构门归 **check 入口**（A2）。

## 10. 治理链（CI workflows）

| workflow | 触发 | 职责 |
|---|---|---|
| `bridge-gate` | push main / PR（paths: combos.yaml, combos/**） | clone 全部底座 → `check --all`；未对齐 **阻止合并**（组合变更的质量门） |
| `check-drift` | `workflow_dispatch`（底座 CI 收 params.json 变化信号，载荷 base_repo + base_version） | clone 受影响底座 → `check --base-repo/--base-version`；有漂移开/更新、对齐则关闭按 base_repo 幂等的 drift issue（「经 else 兜底」警告不建 issue） |
| `build-executable` | tag `v*` / `workflow_dispatch` | clone 底座 + `--collect-params bases_params` 烘焙 → PyInstaller 单文件 → artifact / GitHub Release |

**连通闭环**：底座参数变化 → 底座 CI 自检 + `workflow_dispatch` 信号 → 桥 check-drift 对比 combos.yaml 基线 → 未对齐开 issue → 人/AI 改 `combos/<组合>/` 契约模板 + **手动 bump combos.yaml version** → 桥 bridge-gate 门槛校验 → 对齐。

## 11. 边界不变量（不得违背）

1. **桥只管 N≥2**：多单元组合；单模板形态（②-⑥）不进桥，走能力层 generate_single。
2. **只认注册组合**：combos.yaml `units.source` 必须是 bases 注册裸名——不支持显式 URL/本地路径（单端零注册语义不反向长进桥）。
3. **底座一律 clone/baked**：无源码兄弟目录模式；version 由 combos.yaml 钉，clone + checkout。
4. **version 手动维护**：非自动更新——check 漂移基线 + generate checkout 目标，一套值不拆。
5. **CLI 选项数据驱动**：schema 只来自各 unit 底座 params.json；不解析 copier.yml、不手抄参数、无 `-D` 自由透传。
6. **派生/内部参数只读**：`derived:true` 纯派生值与 `project_name`/`project_title` 内部身份不暴露为用户选项、不接受用户传入。
7. **合并 per-edge 属主**：provider 赢、用户参数最高；契约渲染数据 = 实际生效 answers（默认漂移在构造上不存在）。
8. **selection 单一真源**：技术事实在底座 params.json `selection` 区；combo 段只放组合不可约事实；两处都不复制到能力层/壳侧数据。
9. **共享参数 = 全链单一决策（U1）**：≥2 units 同名 = 单值广播，不逐端参数命名空间；逐端差异由各单元私有参数表达。
10. **面分离**：`generate`/内省 = 生成面（能力层经 cli 消费）；`check` = 治理链服务 CI（bridge-gate / check-drift）。治理面 MCP 未来另起（bridge-mcp-server DESIGN §10），**不在生成面暴露 check/写治理操作**。
11. **契约模板纪律**：全必填零默认 + StrictUndefined；条件用共享原生参数；派生值由 copier 算（`when:false`）；`{% yield %}` 仅限文件名。
12. **copier 全链钉版**：桥/底座/协议/CI 同钉一个 copier 版本（当前 9.17.1）——generated_by 参与 verify，版本漂移会破坏对齐。

## 12. 非目标 / 演进

- **R4 + A1（ui-bff-api 三单元链接入时）**：多 provider 共享参数与 merge_order 统一为「最深 provider 赢」；链形校验收紧为单一路径（出入度 + 连通，防星型漏过）。
- **拓扑放宽**：edges 数 = units−1 目前限链形；星型/环型（多 edge 契约）未来再放宽。
- **契约层扩展**：python-vue 组合、更多后端栈、jwt 模式契约补章节——待第二组合/后端 jwt 实现。
- 本仓不做：单端直生成（能力层）、生成 MCP（能力层）、契约维护 Agent（独立治理，见系列后期待办）、视觉成品/便捷方法。
- 新组合/新底座就绪后验证 combo 段「仅不可约」纪律；需要时给 combos.yaml unit 加 kind 机器字段（`list_combos` frontend/backend_kind 过滤）——届时一并评估。

## 13. 相关文档

- [docs/base-onboarding.md](base-onboarding.md) — 新底座/新组合接入 SOP（含 GitHub PAT/Secret/Variable 配置与触发链路）。
- fullstack-param-protocol `SCHEMA.md` — params.json v2 两区 + `selection` 字段集契约（单一真源，SELECTION_FIELDS 引用）。
- bridge-mcp-server `docs/DESIGN.md` — 生成面 MCP（纯 cli 消费本仓生成面；共享参数/面分离定案）。
- series `ai-foundation-memory`（series-overview.md / CLAUDE.md）— 系列元信息与收敛不变量索引。
- 评审归档：ai-foundation-review `reports/fullstack-bridge/…`（按分支/提交/时间）。

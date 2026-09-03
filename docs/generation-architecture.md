# 生成能力架构重构方案（N≥2 契约治理 + 单模板直生成）

> 分支：refactor/nunit-topology ｜ 状态：方向与关键决策定案（Q1–Q4 已拍板），待评审后实施
> 归属：系列生成能力层

## 0. 背景：系列最终要能生成 6 类形态

| # | 形态 | 归属 | 拓扑 | 契约 |
|---|---|---|---|---|
| ① | 前后端分离（前端可含 BFF） | 桥 | 多单元（前端 SPA **或** 前端全栈 + 后端，可 3 单元链） | 逐跳（每 edge 一份） |
| ② | 纯前端全栈（Nuxt+BFF） | 单模板 | 单单元 | 无外部契约 |
| ③ | 纯后端 | 单模板 | 单单元 | 无 |
| ④ | 纯前端 | 单模板 | 单单元 | 无 |
| ⑤ | 纯命令行 | 单模板 | 单单元 | 无 |
| ⑥ | 其它单模板 | 单模板 | 单单元 | 无 |

**核心区分（第一原则）：生成 ≠ 治理。**

- **底座本质 = git 地址 + copier**：`git 仓 + template/ 子目录 + copier.yml`，自描述（参数/choices/默认全在 copier.yml 里）。单模板生成**不需要注册表**——给 git 地址即可。
- **注册表是「治理」概念，只属多端**：多端契约的 version 基线对齐（漂移检查）。单模板无契约、无基线，不碰注册表。
- **桥的存在意义 = 契约对齐，契约只在 N≥2 存在** → 桥只认多单元组合（N 不包括 1）；单模板生成由能力层直出。

## 1. 关键决策定案（Q1–Q4，已拍板）

### Q1：**不引入全局 kind 轴**——接线知识归底座，契约归组合
- 契约模板保持 **per-combo 手写**（`combos/<组合>/`），不建 kind taxonomy 去分支叙述。
- 原因：组合数少、各组合接线差异大（Nuxt 与 Next 同称 fullstack 但接线不同），全局 kind 是过度抽象税；且接线惯例真正单一真源是**各底座自己的 docs**。
- 可复用的「某框架端如何对接（CORS/proxy/SSR 直连）」写成**该底座 docs 固定章节**，契约只按单位引用。
- edge 可带声明数据 `transport: cors | direct`（README/QA 用），**非**模板分支依据。

### Q2：**逐跳契约目录结构**——1 edge = 1 契约文档 + 顶部索引
- 输出侧：
  - 1-edge 组合 → `docs/CONTRACT.md`（= 现状，回归不动）；
  - 多 edge 组合 → `docs/CONTRACT.md`（边界图 + 各 edge 索引）+ `docs/contracts/<edge>.md`。
- 契约源侧：契约 copier 模板 per-combo（`combos/<组合>/copier.yml` 声明全部参数），内含每 edge 一个 `*.md.jinja`；输出文件名按 edge key（`{u1}-{u2}`）数据驱动。多 edge 的中间单元（BFF）横跨两份 edge 文档，其聚合视角由两侧拼出。
- 目录名/文件名一律来自 units/edges key（见 Q3），**无硬编码**。
- 1-edge 源组织是否统一进 `contracts/<edge>/`：**为保回归暂不动**（python-react 维持 `combos/python-react/` 根）；多 edge 组合用 `combos/<组合>/contracts/` 下按 edge 子模板。两套并存的差异在 Phase A 记录、不强行统一。

### Q3：**各端目录名 = units 配置的 key**（取代硬编码 frontend/backend）
- 布局由 units key 驱动：`units: { ui, bff, api }` → `project/ui/ project/bff/ project/api/`；
- key 同时是 copier `project_name` 后缀（`xxx-ui`）；python-react 的 units key 命名为 `frontend`/`backend` → 输出 `frontend/ backend/` 零回归（默认 key 即此，非特判）；
- 契约/README 中所有对目录的硬引用（`frontend/vite.config.ts` 等）**改为按 units key 数据注入渲染**；
- 单模板路径（②–⑥）**不适用**本规则：生成到 `target_dir` 根、无 key/-后缀、README 由底座自带、无 docs/CONTRACT.md——与多端路径明确分界。

### Q4：**彻底删除逃生舱模式（模式 B `--frontend/--backend`）**
- 逃生舱两个原用例均被正式路径接管：单个任意底座 → 能力层 `generate_single(git_url)`（零注册，地址自描述）；多端 ad-hoc 组合 → **不再成立**（无契约即无桥价值，应注册）。
- 多端生成只接受 combos.yaml 注册组合；**未知组合直接拒绝并提示去注册**——「先注册再生成」是硬守则而非退路。
- 连带删除：`validate_cli` 互斥/成对规则、`resolve_pipeline` 按路径匹配逻辑、README「模式 B / git 地址不提供契约」等注记。
- 开发迭代本地改动由模式 A 源码路径（读 `../<source>/template` HEAD）覆盖，无需逃生舱。

## 2. 目标架构（两层双路径）

```
桥壳层            [Claude Code / Hermes / OpenClaw / 自研应用]
                       │ MCP
bridge-mcp-server   能力面 · 薄  ← 6 种形态唯一入口
 ├─ ②-⑥ 单模板: generate_single(git_url, params, dir)  零注册
 ├─ ①   多端  : generate_multi(combo, params, dir)     → shell-out 桥
 └─ 内省   : get_template_params(git_url) / get_combo_params(combo) / list_combos()
              （详情见 bridge-mcp-server docs/DESIGN.md §6）

fullstack-bridge    多端编排与契约治理专家（N≥2）· 保留
  combos.yaml : bases 注册表 + combos（units≥2 + edges + version 基线 + stack）
  integrate.py: N 单元循环 → 逐跳契约渲染（单模式，无逃生舱）
  check.py    : 沿 edges 对齐 / 漂移治理
```

- **②–⑥ 的价值就是轻**：git 地址 + copier，无注册、无契约、无对齐机器。
- 底座安装 `_tasks` 各模板自带，能力层与桥都不知道「CLI 怎么装依赖」。

## 3. 架构优化点

### 优化点 0：combos.yaml → 「多端治理真源」（units≥2 + edges + version），单模板不在此
现状：bases+combos 是双端投影。改成（仅多端形态落入）：

```yaml
bases:                        # 治理注册：裸名→git URL + 多端 version 基线（单模板不查）
  vite-react-spa-template:   https://.../vite-react-spa-template.git
  python-fastapi-template:   https://.../python-fastapi-template.git

combos:
  python-react:              # 两单元 = 现行为（回归不动）；units key=目录名
    units:
      frontend: { source: vite-react-spa-template, version: <sha> }
      backend:  { source: python-fastapi-template, version: <sha> }
    edges: [[frontend, backend]]
    stack: { ... }
  ui-bff-api:                # 独立网关三单元：2 段逐跳契约
    units:
      ui:    { source: vite-react-spa-template, version: <sha> }
      bff:   { source: bff-gateway-template,    version: <sha> }
      api:   { source: python-fastapi-template, version: <sha> }
    edges: [[ui, bff], [bff, api]]   # C1=UI↔BFF, C2=BFF↔真后端
    stack: { ... }
```
- N 不包括 1：combos 里不出现单单元；单模板由 `generate_single` 直出，不注册。
- units 顺序 = YAML 声明顺序 = 目录生成顺序与 key 来源。

### 优化点 1：多端拓扑「双端固定」→「N 单元 + 逐跳契约（N≥2）」
- 现状：integrate.py 硬写两次 copier + 一份契约。
- 改成：combo = `units[]`（≥2）+ `edges[]`；N 单元产生 N-1 段契约；python-react = units=[fe,be], edges=[[fe,be]] 特例，回归不动。**无 N=1 分支**（N=1 不在桥）。

### 优化点 2：单模板直生成（薄核心），不背契约/对齐机器
- 现状：无单单元路径；且常被误以为需要注册。
- 改成：能力层 `generate_single(git_url, params, target_dir)`——地址自描述，clone 指 template/ 后 copier copy。参数内省 `get_template_params(git_url)` 同理。零注册。
- 便捷别名（裸名/常用底座）属**可选 UX**，非架构必需。

### 优化点 3：契约 per-combo + 接线下沉底座（替代原 kind 轴，见 Q1）
- 现状：契约口吻写死「React SPA 浏览器 CORS」。
- 改成：契约模板 per-combo 手写，叙述/接线章节按其实际单元种类撰写；可复用的「端对接」惯例写成该底座 docs 固定章节，契约按单位引用。edge `transport` 声明只供 README/QA。

### 优化点 4：合并优先级「全局写死」→「per-edge 语义」
- 现状：merge_answers 写死 user > backend > frontend（后端主契约）。
- 改成：每条 edge 定义「契约属主」端；中间单元（BFF）两侧身份不同——对 UI 是服务端、对真后端是消费端。

### 优化点 5：对齐/检查链只在「多端组合（有 edges）」生效
- 现状：check.py `for end in ("frontend","backend")` 遍历假设所有组合双端。
- 改成：沿 edges 遍历；无 edges（单模板）不在桥，其 params 漂移由底座自己的 params-check CI 兜。

### 优化点 6：params.json 协议边界——只服务治理，不服务生成
- 单模板直接 copier 生成**不需要** params.json；它只用于「底座参数变 → 多端契约/组合是否跟随」的治理闭环。协议仓零改动。

### 优化点 7：删除逃生舱（模式 B），多端只认注册组合（见 Q4）
- CLI 收敛单模式；`validate_cli` / `resolve_pipeline` 匹配逻辑删除；未知组合直接拒绝并提示去注册。

### 优化点 8：目录/命名/引用全由 units key 数据驱动（见 Q3）
- 布局 `project/<key>/`、project_name 后缀 `-<key>`、契约/README 目录引用按 key 注入；python-react 用默认 key `frontend/backend` 保持回归。

### 优化点 9：MCP 能力面随形态拆工具 + 可执行分发延续
- `generate_single` / `generate_multi` / `get_template_params` / `get_combo_params` / `list_combos`（见 DESIGN §6）。
- dist/integrate 单文件已打包多端生成；单模板若需分发 = 薄核心可执行；运行形态（源码/可执行）每层可配置，沿用 combos.py frozen 机制。

## 4. 逐跳契约模型与目录（Q2）

N 单元链有 N-1 段相邻接口，每段一份契约；中间单元（BFF）既是 C1 服务端又是 C2 消费端，answers 两侧均作输入。`frontend-fullstack` 自带服务端故可与真后端直接成契约（内嵌版）；`bff` 为独立网关（三单元链）。

输出目录（多端通用）：

```
project/
├── <units key>/…            # 每单元一个目录（Q3）
├── docs/
│   ├── CONTRACT.md          # 边界图 + 各 edge 索引（1-edge = 契约全文，回归）
│   └── contracts/
│       └── <edge>.md        # 每 edge 一份（多 edge 时）：共享接口 + 两端侧
└── README.md
```

单模板（②–⑥）输出：`target_dir` 根（底座自带结构 + README），无 docs/CONTRACT.md。

## 5. 依赖顺序（实施 Phase）

- **Phase A**：优化点 0+1+5+7 —— combos.yaml 泛化（units≥2/edges）+ integrate.py N 单元 + 删逃生舱 + check 沿 edges（python-react 回归不动）。
- **Phase B**：优化点 2+6+8 —— 单模板直生成 + params.json 边界 + units-key 布局/引用数据化（解锁纯后端/纯前端，零注册）。
- **Phase C**：优化点 3+4 —— per-combo 契约接线下沉 + per-edge 合并（解锁类型 ① 含 BFF/3 单元链）。
- **Phase D**：优化点 9 —— MCP 双工具面 + 可执行分发；新底座（Nuxt fullstack / BFF 网关 / CLI）陆续接入。

## 6. 组件改动清单（汇总）

| 组件 | 改动 |
|---|---|
| combos.yaml | 退化为多端治理真源：units≥2 + edges + version 基线；单模板不注册 |
| integrate.py | 双 copier 硬写 → N 单元循环（N≥2）+ 逐跳契约；删逃生舱；无 N=1 分支 |
| 多端契约模板 | per-combo 手写，按 units key 引用底座 docs 接线；edge transport 声明 |
| check.py | 沿 edges 遍历（N≥2） |
| bridge-mcp-server | DESIGN §6：generate_single / generate_multi / get_template_params / get_combo_params / list_combos |
| project-README 模板 | 目录结构按 units key 渲染；单模板由底座自带 README，能力层不另造 |
| 新底座（后续） | nuxt-fullstack、bff-gateway、cli——一律 git+template/+params.json 三件套 |
| fullstack-param-protocol | 零改动（治理与生成解耦） |

## 7. 守的分寸（防过度抽象）

- 单模板生成**零注册**：底座 = git 地址 + copier，地址自描述。
- N 不包括 1：桥不出现 N=1 分支；N=1 是能力层直出。
- **不建 kind 轴**：接线归底座 docs、契约归组合，edge transport 只作声明数据。
- python-react 全程回归不动（默认 units key = frontend/backend、1-edge 契约 = docs/CONTRACT.md）；新增能力以「可选的 units≥2 / edges / key / version」表达，向后兼容。
- 逃生舱删除：多端只认注册组合，未注册即拒绝提示，倒逼「先注册再生成」。

## 8. 参考
- bridge-mcp-server docs/DESIGN.md（能力面设计）
- series-overview.md（系列元信息）

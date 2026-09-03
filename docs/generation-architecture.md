# 生成能力架构重构方案（N≥2 契约治理 + 单模板直生成）

> 分支：refactor/nunit-topology ｜ 状态：方案定稿（待评审后实施）｜ 归属：系列生成能力层

## 0. 背景：系列最终要能生成 6 类形态

| # | 形态 | 归属 | 拓扑 | 契约 |
|---|---|---|---|---|
| 1 | 前后端分离（前端可含 BFF） | 桥 | 双单元（前端 SPA **或** 前端全栈 + 后端） | 跨端（前端侧按 kind 分支） |
| 2 | 纯前端全栈（Nuxt+BFF） | 单模板 | 单单元 | 无外部契约 |
| 3 | 纯后端 | 单模板 | 单单元 | 无 |
| 4 | 纯前端 | 单模板 | 单单元 | 无 |
| 5 | 纯命令行 | 单模板 | 单单元 | 无 |
| 6 | 其它单模板 | 单模板 | 单单元 | 无 |

**核心区分（本方案第一原则）：生成 ≠ 治理。**

- **底座本质 = git 地址 + copier**：`git 仓 + template/ 子目录 + copier.yml`，自描述（参数/choices/默认全在 copier.yml 里）。单模板生成**不需要注册表**——信息全在地址里，给 git 地址即可。
- **注册表是「治理」概念，只属多端**：裸名→本地兄弟目录映射（源码模式开发便利）、多端契约的 version 基线对齐（漂移检查）。单模板无契约、无基线，不碰注册表。
- **桥的存在意义 = 契约对齐，而契约只在 N≥2 存在** → 桥只认多单元组合（N 不包括 1）；单模板生成由能力层直出。

## 1. 目标架构（两层）

```
桥壳层            [Claude Code / Hermes / OpenClaw / 自研应用]
                       │ MCP
bridge-mcp-server   能力面 · 薄  ← 6 种形态唯一入口
 ├─ 类型 3-6（单模板）: generate_single(git_url, params, target_dir)
 │                     地址自描述 → clone → 指向 <repo>/template → copier copy → _tasks 装依赖
 ├─ 类型 1-2（多端）  : generate_multi(combo) → shell-out fullstack-bridge（N 单元 + 契约链）
 └─ 底座参数自省      : get_params(git_url | combo) —— 给地址就 clone 内省 copier.yml，不查注册表

fullstack-bridge    多端编排与契约治理专家（N≥2）· 保留
  combos.yaml : bases 注册表 + combos（units ≥ 2 + edges 契约链 + version 基线）
  integrate.py: N 单元循环 → 逐跳契约渲染
  check.py    : 沿 edges 对齐 / 漂移治理
```

- **类型 3-6 的价值就是轻**：git 地址 + copier，无注册、无契约、无对齐机器。
- 底座安装 `_tasks` 各模板自带，能力层与桥都不知道「CLI 怎么装依赖」。

## 2. 架构优化点

### 优化点 0：combos.yaml → 「多端治理真源」（units≥2 + edges + version），单模板不在此
现状：bases+combos 是双端投影。改成（仅多端形态落入）：

```yaml
bases:                        # 治理注册：裸名→git URL + 多端 version 基线（单模板不查）
  vite-react-spa-template:   https://.../vite-react-spa-template.git
  python-fastapi-template:   https://.../python-fastapi-template.git

combos:
  python-react:              # 两单元 = 现行为（回归不动）
    units: { frontend: vite-react-spa-template, backend: python-fastapi-template }
    edges: [[frontend, backend]]
    versions: { frontend: <sha>, backend: <sha> }     # version 基线（现 version 字段）
  nuxt-bff-python:           # 内嵌 BFF + 真后端：两单元 1 契约
    units: { frontend: nuxt-fullstack, backend: python-fastapi-template }
    edges: [[frontend, backend]]
  ui-bff-api:                # 独立网关三单元：2 段逐跳契约
    units: { ui: vite-react-spa-template, bff: bff-gateway, backend: python-fastapi-template }
    edges: [[ui, bff], [bff, backend]]   # C1=UI↔BFF, C2=BFF↔真后端
```
（N 不包括 1：combos 里不出现单单元；单模板由 MCP `generate_single` 直出，不注册。）

### 优化点 1：多端拓扑「双端固定」→「N 单元 + 逐跳契约（N≥2）」
- 现状：integrate.py 硬写两次 copier + 一份契约；逃生舱强制 `--frontend/--backend` 成对。
- 改成：combo = `units[]`（≥2）+ `edges[]`；N 单元产生 N-1 段契约。python-react = units=[fe,be], edges=[[fe,be]] 特例，回归不动。**无 N=1 分支**（N=1 不在桥）。

### 优化点 2：单模板直生成（薄核心），不背契约/对齐机器
- 现状：无单单元路径；且常被误以为需要注册。
- 改成：能力层 `generate_single(git_url, params, target_dir)`——地址自描述，clone 指 template/ 后 copier copy。底座参数自省 `get_params(git_url)` 同理。零注册。
- 便捷别名（裸名/常用底座）属**可选 UX**，非架构必需。

### 优化点 3：角色 kind 轴 → 多端契约/README/命名按 kind 分支
- 现状：契约口吻写死「React SPA 浏览器 CORS」。
- 改成：多端契约叙述/接线章节按单元 kind 分支（jinja `{% if %}`）——SPA 走浏览器 CORS，Nuxt/BFF 走服务端直连/内部跳。一份契约模板服务同一端不同 kind。
- kind 是**多端契约域**概念（frontend-spa / frontend-fullstack / backend-api / bff）；单模板生成不需要 kind（copier.yml 自述）。

### 优化点 4：合并优先级「全局写死」→「per-edge 语义」
- 现状：merge_answers 写死 user > backend > frontend（后端主契约）。
- 改成：每条 edge 定义「契约属主」端；中间单元（BFF）两侧身份不同——对 UI 是服务端、对真后端是消费端。

### 优化点 5：对齐/检查链只在「多端组合（有 edges）」生效
- 现状：check.py `for end in ("frontend","backend")` 遍历假设所有组合双端。
- 改成：沿 edges 遍历；无 edges（单模板）**不在桥**，其 params 漂移由底座自己的 params-check CI 兜。

### 优化点 6：params.json 协议边界——只服务治理，不服务生成
- 写明：单模板直接 copier 生成**不需要** params.json；它只用于「底座参数变 → 多端契约/组合是否跟随」的治理闭环。协议仓零改动。

### 优化点 7：MCP 能力面随形态拆工具
- `generate_single(git_url, params, target_dir)`（类型 3-6，地址自描述）
- `generate_multi(combo, …)`（类型 1-2，shell-out 桥）
- `get_params(git_url | combo)`（单模板内省 copier.yml / 多端读组合参数基线）
- `list_combos()`（多端注册组合菜单，供治理/选择）
- selection 元数据带「形态种类」，跨形态可推荐（单模板选栈 = 用户直接给地址或选底座；多端 = L1/L2/L3）。

### 优化点 8：可执行分发延续
- dist/integrate 单文件已打包多端生成；单模板若需分发 = 薄核心可执行（PyInstaller + frozen 克隆缓存）；运行形态（源码/可执行）每层可配置，沿用 combos.py frozen 机制。

## 3. 逐跳契约模型（类型 1「两者都要」的建模）

N 单元链有 N-1 段相邻接口，每段一份契约模板；中间单元（BFF）既是 C1 服务端又是 C2 消费端，其 answers 两侧均作输入。`frontend-fullstack` 自带服务端故可与真后端直接成契约（内嵌版）；`bff` 为独立网关（三单元链）。

## 4. 依赖顺序（实施 Phase）

- **Phase A**：优化点 0+1+5 —— combos.yaml 泛化（units≥2 / edges）+ integrate.py N 单元 + check 沿 edges（python-react 回归不动）。
- **Phase B**：优化点 2+6 —— 单模板直生成 + params.json 边界文档化（解锁纯后端/纯前端，零注册）。
- **Phase C**：优化点 3+4 —— kind 轴 + 契约 kind-aware 分支 + per-edge 合并（解锁类型 1 含 BFF）。
- **Phase D**：优化点 7+8 —— MCP 双工具面 + 可执行分发；新底座（Nuxt fullstack / BFF 网关 / CLI）陆续接入。

## 5. 组件改动清单（汇总）

| 组件 | 改动 |
|---|---|
| combos.yaml | 退化为多端治理真源：units≥2 + edges + version 基线；单模板不注册 |
| integrate.py | 双 copier 硬写 → N 单元循环（N≥2）+ 逐跳契约；无 N=1 分支 |
| 多端契约模板 | 叙述按参与单元 kind 分支 |
| check.py | 沿 edges 遍历（N≥2） |
| bridge-mcp-server | DESIGN §6 拆 generate_single（git 地址）/ generate_multi（combo）+ get_params + list_combos |
| project-README 模板 | 多端 frontend\+backend 布局分支（单模板由底座自带 README，能力层不另造） |
| 新底座（后续） | nuxt-fullstack、bff-gateway、cli——一律 git+template/+params.json 三件套 |
| fullstack-param-protocol | 零改动（治理与生成解耦） |

## 6. 守的分寸（防过度抽象）

- 单模板生成**零注册**：底座 = git 地址 + copier，地址自描述；不给单模板造注册表/治理。
- N 不包括 1：桥不出现 N=1 分支；N=1 是能力层直出，不背契约机器。
- python-react 全程回归不动；新增能力以「可选的 units≥2 / edges / kind / version」表达，向后兼容。

## 7. 参考
- bridge-mcp-server docs/DESIGN.md（能力面设计）
- series-overview.md（系列元信息）

# 生成能力架构重构方案（N 单元拓扑 + 单模板薄核心）

> 分支：refactor/nunit-topology ｜ 状态：方案定稿（待评审后实施）｜ 归属：系列生成能力层

## 0. 背景：系列最终要能生成 6 类形态

| # | 形态 | 拓扑 | 契约 | 所需底座 | 现有支持 |
|---|---|---|---|---|---|
| 1 | 前后端分离（前端可含 BFF） | 双单元（前端 SPA **或** 前端全栈 + 后端） | 跨端（前端侧按 kind 分支） | 现有 + Nuxt 类前端全栈底座 | 仅「SPA+FastAPI」一种 |
| 2 | 纯前端全栈（Nuxt+BFF） | 单单元 frontend-fullstack | 无外部契约 | Nuxt fullstack 底座（新） | ❌ |
| 3 | 纯后端 | 单单元 backend | 无 | 现有 python-fastapi | 底座可 copier，桥/MCP 菜单表达不了 |
| 4 | 纯前端 | 单单元 frontend-spa | 无 | 现有 vite-\* | 同上 |
| 5 | 纯命令行 | 单单元 cli | 无 | CLI 底座（新/后续） | ❌ |
| 6 | 其它单模板 | 单单元 generic | 无 | 任意 copier 模板 | ❌（逃生舱强制成对） |

**根因**：现有 fullstack-bridge 把两件正交的事焊死——(a) 模板「形态种类 kind」与 (b) 编排「拓扑结构」耦合在双端模型里；单模板形态被契约/对齐机器绑架，多端形态被「仅 SPA+FastAPI」限定。

**总纲**：解耦 kind 与拓扑；单模板（类型 3-6）走轻量薄核心，多端（类型 1-2）走契约对齐专家；两轴都数据驱动、向后兼容。

## 1. 目标架构（两层生成能力）

```
桥壳层            [Claude Code / Hermes / OpenClaw / 自研应用]
                       │ MCP
bridge-mcp-server   能力面 · 薄  ← 6 种形态唯一入口
 ├─ 类型 3-6（单模板）: 薄核心直调底座 copier —— 无契约/对齐机器
 ├─ 类型 1-2（多端）  : shell-out fullstack-bridge（N 单元编排 + 契约链）
 └─ 读 fullstack-bridge/combos.yaml（注册表单一真源）

fullstack-bridge    多端编排与契约专家（N 单元 + 逐跳契约）· 保留
  combos.yaml : templates 注册表 + combos（N 单元 + edges 契约链）
  integrate.py: N 单元循环 → 逐跳契约渲染
  check.py    : 沿 edges 对齐
```

- 类型 3-6 的价值就是轻：注册 + 版本钉 + 生成，不背契约/merge/check。
- 底座安装 `_tasks` 各模板自带，薄核心与桥都不知道「CLI 怎么装依赖」。

## 2. 架构优化点

### 优化点 0：combos.yaml → 「模板角色注册表 + 组合拓扑声明」单一真源
现状：双端投影，kind 散落（stack 字符串、契约口吻）。改成：

```yaml
templates:                    # 底座角色注册表：kind 驱动下游
  vite-react-spa-template:   { kind: frontend-spa }         # consumer
  python-fastapi-template:   { kind: backend-api }          # provider
  nuxt-fullstack-template:   { kind: frontend-fullstack }   # 内嵌 BFF：consumer+provider
  bff-gateway-template:      { kind: bff }                  # 独立网关（未来）

combos:
  python-react:              # 两单元 = 现行为（回归不动）
    units: { frontend: <tpl>, backend: <tpl> }
    edges: [[frontend, backend]]
  nuxt-bff-python:           # 内嵌 BFF + 真后端：两单元 1 契约
    units: { frontend: nuxt-fullstack, backend: python-fastapi }
    edges: [[frontend, backend]]
  ui-bff-api:                # 独立网关三单元：2 段逐跳契约
    units: { ui: vite-react-spa, bff: bff-gateway, api: python-fastapi }
    edges: [[ui, bff], [bff, api]]      # C1=UI↔BFF, C2=BFF↔真后端
  backend-only:              # 单单元无契约（纯后端）
    units: { app: python-fastapi }
```
（bases git 地址注册表并入 templates，source 裸名 → git URL 解析不变。）

### 优化点 1：拓扑「双端固定」→「N 单元 + 逐跳契约（units/edges）」
- 现状：integrate.py 硬写两次 copier + 一份契约；逃生舱强制 `--frontend/--backend` 成对。
- 改成：combo = `units[]` + `edges[]`；N 单元产生 N-1 段契约；单单元 = 无 edges = 无契约。python-react 是 units=[fe,be], edges=[[fe,be]] 的特例，回归不动。

### 优化点 2：角色 kind 轴 → 契约/README/命名按 kind 分支
- 现状：契约口吻写死「React SPA 浏览器 CORS」。
- 改成：契约叙述/接线章节按参与单元 kind 分支（jinja `{% if %}`）——SPA 走浏览器 CORS，Nuxt/BFF 走服务端直连/内部跳。一份契约模板服务同一端不同 kind。

### 优化点 3：单模板形态走薄生成核心，不背契约/对齐机器
- 现状：无单单元路径（类型 3/4 菜单层表达不了）。
- 改成：薄核心（并入 bridge-mcp-server）直调底座 copier；注册 + 版本钉 + 生成，无 merge/check。

### 优化点 4：合并优先级「全局写死」→「per-edge 语义」
- 现状：merge_answers 写死 user > backend > frontend（后端主契约）。
- 改成：每条 edge 定义「契约属主」端；中间单元（BFF）两侧身份不同——对 UI 是服务端、对真后端是消费端。

### 优化点 5：对齐/检查链只在「有 edges 的组合」生效
- 现状：check.py `for end in ("frontend","backend")` 遍历假设所有组合双端。
- 改成：沿 edges 遍历；无 edges 单单元跳过桥级 check（params 漂移由底座 params-check CI 兜）。

### 优化点 6：params.json 协议边界——只服务治理，不服务生成
- 现状：易误以为生成依赖 params.json。
- 改成：写明——单模板直接 copier 生成不需要 params.json；它只用于「底座参数变 → 桥契约/组合是否跟随」的治理闭环。协议仓零改动。

### 优化点 7：MCP 能力面随拓扑拆工具
- 现状：bridge-mcp-server DESIGN 只有 `generate_project(combo)` 一套。
- 改成：`generate_single(template,…)`（3-6）/ `generate_multi(combo,…)`（1-2）；`list_templates` / `list_combos`；selection 元数据带「形态种类」，跨形态可推荐。

### 优化点 8：可执行分发延续
- dist/integrate 单文件已打包多端生成；薄核心如需分发按同模式（PyInstaller + frozen 克隆缓存）；运行形态（源码/可执行）每层可配置，沿用 combos.py frozen 机制。

## 3. 逐跳契约模型（类型 1「两者都要」的建模）

N 单元链有 N-1 段相邻接口，每段一份契约模板；中间单元（BFF）既是 C1 服务端又是 C2 消费端，其 answers 两侧均作输入。`kind: frontend-fullstack` 表示该单元自带服务端，故可与真后端直接成契约（类型 1 内嵌版）；`kind: bff` 表示独立网关（三单元链）。

## 4. 依赖顺序（实施 Phase）

- **Phase A**：优化点 0+1+5 —— combos.yaml 泛化（units/edges）+ integrate.py N 单元 + check 沿 edges（python-react 回归不动）。
- **Phase B**：优化点 3+6 —— 单单元路径 + params.json 边界文档化（解锁纯后端/纯前端）。
- **Phase C**：优化点 2+4 —— kind 轴 + 契约 kind-aware 分支 + per-edge 合并（解锁类型 1 含 BFF）。
- **Phase D**：优化点 7+8 —— MCP 双工具面 + 可执行分发；新底座（Nuxt fullstack / BFF 网关 / CLI）陆续接入。

## 5. 组件改动清单（汇总）

| 组件 | 改动 |
|---|---|
| combos.yaml | templates 角色表；combo → units + edges；contract 可缺省 |
| integrate.py | 双 copier 硬写 → N 单元循环 + 逐跳契约；布局/命名按 topology+role |
| 契约模板 | 叙述按参与单元 kind 分支 |
| check.py | 沿 edges 遍历；无 edges 跳过 |
| bridge-mcp-server | DESIGN §6 拆 generate_single / generate_multi + list_templates / list_combos |
| project-README 模板 | 单单元项目根 / 多单元 frontend\+backend 布局分支 |
| 新底座（后续） | nuxt-fullstack、bff-gateway、cli、generic——一律 git+template/+params.json 三件套 |
| fullstack-param-protocol | 零改动（治理与拓扑解耦） |

## 6. 守的分寸（防过度抽象）

- 不把单模板形态硬塞进双端契约模型；单单元价值就是轻。
- 不为形式统一让 integrate.py 对所有形态走同一套 merge/check。
- python-react 全程回归不动；新增能力以「可选的 units/edges/kind」表达，向后兼容。

## 7. 参考
- bridge-mcp-server docs/DESIGN.md（能力面设计）
- series-overview.md（系列元信息）

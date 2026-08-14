# fullstack-bridge 重构设计方案

> 状态：已拍板（2026-08-14），分两阶段实施。本文档是实施参照，含决策记录、两链设计、实证结论、已知漂移规划。

## 1. 背景与问题

fullstack-bridge 是系列**桥接层**：把前端底座 + 后端底座 + 裁剪契约整合成「前后端一体」大目录。当前实现的问题：

- **工具链不统一**：前端/后端均用 copier，桥的契约却用自研 jinja2 渲染器（`bin/render.py`），是系列里唯一不统一处
- **参数副本易漂移**：`integrate.sh` 手动维护各底座参数副本（case 分支 + 逐条 `-d` 接线），底座参数变化时桥不同步
- **契约与底座不同步**：已实证 4 处漂移（见 §9），根因是契约渲染数据只含 CLI 传入值、不含底座实际生效的默认值

**目标**：
1. 工具链统一——契约也做成 copier 模板，`render.py` 退役
2. 对齐协议——底座通过 `params.json`（钩子经 copier 内省生成、底座自维护）与桥对齐
3. 检查链——底座↔本项目↔契约 未对齐时告警
4. 契约零默认闭环——契约模板全必填零默认，喂生成后实际参数，默认漂移在构造上不存在

## 2. 决策记录（2026-08-14 拍板）

| # | 决策项 | 结论 |
|---|---|---|
| ① | 桥的载体 | **全 Python**（`integrate.py`） |
| ② | 契约渲染喂值 | **桥解析两份 answers → 合并 → `-d` 全传**；合并不是简单拼接，须与用户传入参数**剔除去重**（用户参数优先） |
| ③ | 检查链「本项目参数」基线 | **= 组合契约模板 copier.yml 声明的参数** |
| ④ | params.json schema | **全量参数（含派生），派生参数标注 `derived`，须含 source hash** |
| ⑤ | 底座钩子与 CI | **钩子仅生成（不拦截本地提交）**；base CI 双职责：①自检 params.json==copier.yml，失败**阻止合并**（base 本地硬门槛，无跨仓时序问题）；②探测 params.json 变化 → **物理通知**桥接方（不阻塞）。跨仓对齐检查（check.py）完全在桥侧，与 base CI 解耦 |
| ⑥ | CLI 组合形态 | **缩写与显式 `--frontend/--backend` 两种模式互斥**；`--frontend/--backend` 必须成对出现（**逃生舱**，治理属注册组合）；**底座必须 git 仓**（检查链依赖 git 基线，非 git 直接拒绝）；缩写 → 模板映射独立在 `combos.yaml` 维护（见 §4.1） |
| ⑦ | 已知漂移修复 | **先规划**（§9），不在本期实现 |
| ⑧ | 实施范围 | **分阶段**：阶段 1 = params.json 协议 + 检查链（治理先行）；阶段 2 = 契约迁移 + CLI 改造 |
| ⑨ | 底座钩子+校验工具归属 | **独立小仓**（协议仓）：`gen-params.py` + params.json schema 规范 + CI 校验脚本；各底座**钉版本 vendored** 接入（见 §5.3） |

## 3. 目标架构

```
fullstack-bridge/                     # 桥接层（薄编排 + 组合契约模板）
├── integrate.py                      # 桥编排（Python）
├── check.py                          # 检查链入口（治理告警）
├── combos.yaml                       # 组合映射（缩写 → 前端/后端/契约，加组合只改这里）
├── combos/
│   └── python-react/                 # 契约 copier 模板（桥按组合维护）
│       ├── copier.yml                #   全必填零默认 + _envops StrictUndefined
│       └── CONTRACT.md.jinja         #   全量契约，按条件裁剪
│   └── python-vue/                   # （未来组合 = 加一个目录）
└── ...

底座仓库（各底座自维护）:
├── template/                         # copier 模板体
├── copier.yml                        # 参数真源（作者改它）
├── params.json                       # 对齐协议（钩子经 copier 内省生成，与 copier.yml 原子提交）
└── bin/gen-params.py（协议仓 vendored 副本）+ pre-commit 钩子
```

**两条链**：

```
生成链：任务输入参数 → copier 前端/后端（--frontend/--backend 本地或 git）
                     → 读两端 .copier-answers.yml → 与用户参数剔除合并
                     → 契约 copier 模板渲染（全必填零默认 + StrictUndefined）

检查链：读底座 params.json → 与组合契约模板参数对齐? → 未对齐 → 通知
                            → 对齐 → 与契约对齐? → 未对齐 → 通知
```

## 4. 生成链设计

### 4.1 CLI

两种模式，**互斥**：

```bash
# 模式 A：组合缩写（查 combos.yaml 得 frontend/backend/contract）
integrate.py python-react my-app --api-prefix /v2 --auth-mode opaque -D with_taskqueue=none ...

# 模式 B：显式模板（--frontend/--backend 必须成对出现，不可与缩写混用）
integrate.py my-app \
  --frontend <本地模板目录|git地址> --backend <本地模板目录|git地址> \
  --api-prefix /v2 --auth-mode opaque -D with_taskqueue=none ...
```

- **互斥规则**：模式 A（组合缩写）与模式 B（`--frontend/--backend`）**不可同时使用**，同时出现 → 报错
- **成对规则**：`--frontend` 与 `--backend` **必须同时出现**，只给其一 → 报错
- **模式 B 的契约模板**：在 `combos.yaml` 中按 **(frontend, backend) 匹配已注册组合** → 复用其契约模板；未匹配 → 报错「未注册组合，无契约模板」（提示先在 combos.yaml 注册）。**模式 B 是逃生舱**：治理（check）属于 combos.yaml 注册的组合，显式覆盖的底座路径须为 git 检出（非 git 直接拒绝）

组合缩写 → 前端/后端/契约 的映射维护在 **`combos.yaml`**（独立文件，加新组合只改它 + 加 `combos/<combo>/` 契约模板目录，**不动 integrate.py**）：

  ```yaml
  # combos.yaml — 组合 → 模板映射（加新组合只改这里）
  combos:
    python-react:
      frontend:
        source:  vite-react-spa-template    # 系列底座名 → ../<name>/template；或本地目录 / git 地址
        version: <git-ref>                  # 对齐时的底座版本（commit/tag），check 以此为基线
      backend:
        source:  python-fastapi-template
        version: <git-ref>
      contract: python-react                # 契约模板目录 combos/<combo>/（可省略，按约定推断）
    python-vue:
      frontend:
        source:  vite-vue-spa-template
        version: <git-ref>
      backend:
        source:  python-fastapi-template
        version: <git-ref>
      contract: python-vue
  ```

- 模板源解析规则：`frontend/backend.source` 值为系列底座名（裸名）→ 解析为 `$BRIDGE_DIR/../<name>/template`；以 `/`、`./`、`../` 或 `git@`/`https://` 开头 → 当作显式本地路径 / git 地址原样使用。**底座必须是 git 仓**（检查链依赖 `params.json` version 基线）——非 git 本地目录在整合时直接拒绝
- **`version`（对齐基线，手动维护）**：记录该组合**已复核/对齐到**的底座 git 版本，**非自动更新**。check.py 用它做基线——读 **pinned 版本的 params**（对齐校验）vs **当前 params**（漂移检测），底座从 v_old 走到 v_new 即判漂移、通知跟进。本地目录底座同样记其 HEAD commit
- **version 的 bump 是人工确认动作**：check-drift 检出漂移并被处理时，fix PR 必须**手动更新 version**（标记「已复核新版本」）——**无论契约模板是否改动**：base 新增参数但契约决定不覆盖时也要 bump，否则漂移标志一直挂着。桥 CI 门槛对此有天然约束：契约声明了 pinned 版本没有的参数 → 检查失败，强制要求 bump（防止「改了契约忘了 bump 版本」）
- `--frontend/--backend` 接受**本地目录或 git 地址**；git 地址克隆到缓存目录，模板交给 copier（copier 原生支持 git URL 作 src_path），`params.json` 从克隆读，生成时记 `base@commit`
- 该映射由 `integrate.py` 与 `check.py` **共享**（单一事实来源）
- **`-D key=value` 通用透传（可扩展的关键）**：任意底座参数直接透传给前端/后端 copier（copier 只用各自声明的，未声明的静默忽略），并进入契约渲染数据（若契约模板声明）。**新增底座参数无需改桥 CLI**——用户用 `-D new_param=value` 即可；常用参数再补精选别名（如 `--auth-mode` 等价 `-D auth_mode=opaque`）
- 精选别名覆盖常用逻辑参数（项目名、description、api-base-url、auth-mode、with-db/redis/child-app、api-prefix）；其余一律 `-D` 透传

### 4.2 前端/后端生成

与现状一致：`copier copy <template> <dest> -d ... --trust`（两端均执行 `_tasks`，含 `auth_mode=none` 条件裁剪与依赖安装）。

### 4.3 读 answers → 合并剔除 → 契约渲染

1. 读 `frontend/.copier-answers.yml` 与 `backend/.copier-answers.yml`（YAML → pyyaml）
2. **剔除内部字段**：所有 `_` 前缀（`_src_path`、`_commit`、`_external_data` 等）
3. **用户参数剔除去重**：用户 CLI 传入的每个参数**优先**，以其值为准（逻辑层参数，如原始项目名、description）；answers 中同名值不重复传入——端特有的后缀名（`project_name=xxx-frontend/xxx-backend`）即被此规则排除
4. 其余参数按端取值：后端参数（`auth_mode/with_db/with_redis/with_child_app/api_prefix/child_apps_raw`…）取 backend answers；前端参数（`api_base_url`…）取 frontend answers
5. **`-d` 全传**给契约 copier 模板：`copier copy combos/python-react $PROJECT/docs -d key=value... --defaults`
   - 值经字符串往返（answers 的 bool/num → 字符串 → copier 按契约 copier.yml 声明的 `type` 再强转），类型往返安全
6. 契约模板 `_envops: {undefined: "jinja2.StrictUndefined"}`：引用未声明参数 → 硬报错

> 依据：copier 支持**无默认值的必填参数**，漏传硬报错 `Question "x" is required`（实测）；契约模板声明全必填零默认 → 无默认值可漂移。

## 5. 对齐协议（params.json）

### 5.1 归属与生成

- **位置**：各底座仓库**根目录** `params.json`
- **维护方**：底座项目自己（桥只是消费者）
- **生成**：底座 pre-commit 钩子调 `bin/gen-params.py`，经 **copier 内省**（`Template.questions_data`）从 copier.yml 导出参数 schema → 写 `params.json`（**best-effort，不拦截提交**）
- **base CI 双职责**：
  1. **自检**：校验 `params.json` 与当前 copier.yml 一致（比对 `source_copier_yml_hash`）；失败 → **阻止合并**——base 本地正确性硬门槛，无跨仓依赖，可安全阻止
  2. **变更探测 + 信号**：探测 `params.json` 相对上次提交有变化 → **`workflow_dispatch` 触发桥仓 `check-drift` workflow**（事件驱动信号，不阻塞）——桥 workflow 跑 check.py 产出 diff + 影响面报告，开/更新 issue，供人/AI 处理并人审核
- **时序依据（误解已解除）**：早前担心「CI 里跑本项目（桥）的检查链有时序问题」，实际 base CI 只做 **base 本地自检**（无跨仓依赖、可安全阻止）；**跨仓对齐检查（check.py）完全在桥侧**，由 base 变更信号（workflow_dispatch）驱动 / 桥侧 CI 门槛 / 手动触发。base 不跑桥的检查 → 无跨仓时序耦合。钩子只做便利生成（不拦截本地提交），与 CI 硬门槛配合

### 5.2 Schema

```json
{
  "schema_version": 1,
  "source_copier_yml_hash": "sha256:abc...",
  "generated_by": "copier-introspect@9.17.0",
  "params": {
    "auth_mode": {
      "type": "str",
      "choices": [
        { "value": "none" },
        { "value": "opaque" },
        { "value": "jwt", "disabled": true, "reason": "已设计、暂未实现（见模板 DESIGN.md）" }
      ],
      "default": "opaque",
      "derived": false
    },
    "with_db":    { "type": "bool", "default": true,  "derived": false },
    "child_apps": { "type": "yaml",                    "derived": true  },
    "child_apps_raw": { "type": "str", "default": "backend", "derived": false }
  }
}
```

- **全量参数**（含派生），`when:false` 派生参数标 `"derived": true`
- **choices 结构化**：`{value}` = 启用；`{value, disabled: true, reason}` = 禁用（copier.yml 里带 validator 的未实现选项）——检查 2 据此**只对 enabled choices** 做契约覆盖校验，不会误要求覆盖未实现取值
- **`schema_version`**：params.json 协议/schema 版本（区别于 combos.yaml 里底座的 git `version`）；桥按它对齐协议仓版本
- **`source_copier_yml_hash`**：防静默过期——桥/CI 可校验 params.json 与当前 copier.yml 是否一致
- 桥读取用内置 `json`，零 copier 依赖

> 依据：copier 内省入口（`questions_data`）是 deprecated 内部 API——脆弱点被关在底座钩子（生成时、钉 copier 版本），桥永远消费稳定的已提交 JSON。

### 5.3 协议仓（独立小仓，决策 ⑨）

底座钩子与校验工具独立成仓（工作名如 `ai-foundation-base-tools`），是 params.json **协议的唯一真源**：

- **仓内容**：`gen-params.py`（copier 内省 → params.json，generate / verify 两模式）+ params.json **schema 规范** + CI 校验脚本
- **接入方式**：各底座**钉版本 vendored**（提交一份工具 + 记录版本号），不依赖运行时拉取/安装
- **桥的消费**：桥按协议版本读 params.json——桥与各底座对 schema 的一致，以协议仓版本号为协调点
- **理由**：params.json 跨 3+ 底座 + 桥共享，单一真源 + 版本化（改一次全底座生效，4 处 schema 一致）；「底座自维护 params.json」不受影响——钩子仍在各仓库，只是生成器代码共享
- **防 vendored 漂移**：vendored 副本可能因底座不更新而过期 → base CI **从协议仓 fetch 钉版本的 gen-params** 重生成比对（**不能用过期的 vendored 副本自证**——旧工具验证旧产物是循环验证），或交叉核对 params.json 的 `generated_by`/`source_copier_yml_hash`，不一致即物理通知
- **更新机制**：协议仓发版本 → 各底座更新 vendored 副本（版本号随提交记录）；桥侧检查链按协议版本兼容

## 6. 检查链设计

**触发（信号驱动，方案 1）**：check.py 在桥侧，触发绑定「底座变更事件」，不绑定生成动作：

1. **base CI 信号（主触发）**——底座 params.json 变化 → base CI `workflow_dispatch` 触发桥仓 `check-drift` workflow，**载荷携带 base 仓库 + commit/tag（v_new）**；workflow 接收后把 v_new **作为参数配置进 check.py**（`--base-repo --base-version`）→ 产出 diff + 影响面报告 → 开/更新 issue（供人/AI 处理，最终人审核）。**此 check.py 只读不写**：读 combos.yaml（用该 base 的组合 + pinned 版本 v_old）+ 信号载荷的 v_new，两侧对比出报告，**不改任何状态**；version bump 只发生在后续 fix PR（见下）。**信号必须携带 commit/tag 而非「读 base HEAD」**——桥 CI 无 base checkout，且 base HEAD 是移动目标，信号版本才是精确触发点。check.py 取 base@v_new 的 params.json：**从 base 仓库 fetch**（`git show <commit>:params.json`，CI 有网络）；或**载荷直接携带 params.json diff**（免 fetch，避开 base 仓库可达性）
2. **桥侧 CI / pre-commit 门槛（补强 1）**——桥改动 `combos/` 契约模板或 `combos.yaml` 时，桥 CI/pre-commit 跑 check.py 验证组合与底座 params（pinned 版本）对齐，未对齐**阻止合并**——「信号驱动的产物（改文档 PR）」在合并前被验证，闭环闭合
3. **独立入口手动**——`check.py --combo <缩写|--frontend/--backend> [参数同 integrate.py 模式]`（维护者处理 base 信号开的 issue 时使用）

> 说明：
>
> - 生成过程**不承担对齐检查**——生成只保留硬正确性门槛（契约模板全必填 + StrictUndefined）；对齐漂移由信号驱动循环处理，生成不被该循环打扰。
> - **fix PR 的内容**：改 `combos/<combo>/` 契约模板（若需要）+ **手动 bump `combos.yaml` 的 version**（标记已对齐到新底座版本，**无论契约是否改动**）——桥 CI 门槛据此校验，防「改了契约忘了 bump 版本」。

### 检查 1：底座 ↔ 本项目（组合契约模板参数）

- 读底座 `params.json`（前端 + 后端全量参数）——**pinned 版本**（combos.yaml 记的基线）做对齐校验，**当前/信号版本**做漂移检测
- 读 `combos/<combo>/copier.yml` 声明的参数（「本项目参数」基线）
- **子集对齐（硬门槛）**：契约声明参数 ⊆ 两端底座参数并集（名称/类型/choices 兼容）——拦「契约引用了底座没有的参数」（如契约声明了 pinned 版本没有的参数 → 强制要求 bump 版本）
- **漂移检测（软信号，由 base CI 变更通知送达）**：底座 pinned vs 当前/信号版本 params 有变化 → 通知「底座已推进，需复核组合是否跟进」——「底座新增参数而契约未覆盖」的跟进由此驱动；是否给契约加参数是**人工判断**（可能决定不覆盖，仅 bump 版本）

### 检查 2：参数 ↔ 契约（取值覆盖）

- 对每个参数，底座 `params.json` 的 enabled choices vs 契约模板 `{% if x == 'v' %}` 覆盖的取值（启发式扫描 + `{% else %}` 兜底判断）
- **未对齐 → 通知**：底座新增取值（如 `auth_mode` 加 `jwt`）而契约未覆盖

> 存在性检查（契约引用未声明参数）由 StrictUndefined 在渲染时硬保证，不靠检查链。

## 7. 阶段计划

### 阶段 1（治理先行）：params.json 协议 + 检查链

- 协议仓：`gen-params.py`（copier 内省）+ params.json schema 规范 + CI 校验脚本
- 三个底座：接入协议仓（钉版本 vendored）+ pre-commit 钩子（仅生成）+ CI 自检（失败阻止合并）+ CI 变更探测 `workflow_dispatch` 信号 + 提交 `params.json`
- 桥：加 `combos.yaml`（含各底座 **version 基线**）+ `combos/python-react/` 骨架（**仅 copier.yml 声明参数，作检查 1 基线——决策 ③；完整契约模板在阶段 2**）+ `check.py` + `check-drift` workflow + 桥 CI/pre-commit 门槛（改动 combos 时验证对齐）
- 验证：改底座 copier.yml（加参数/改取值）→ 钩子生成 params.json → base CI 自检 → dispatch 桥 `check-drift` → check.py 报未对齐 → 改 combos 模板 + 更新 version 基线 → 桥 CI 验证 → 对齐闭环

### 阶段 2：契约迁移 + CLI 改造

- 契约迁移为 copier 模板：`combos/python-react/`（全必填零默认 + `_envops` StrictUndefined + `CONTRACT.md.jinja`）；`render.py` 退役
- `integrate.py`：CLI（缩写 + `--frontend/--backend` 覆盖）、生成链（answers 合并剔除喂契约）
- 按 §9 规划一并修契约内容漂移
- 验证：e2e 生成 python-react，契约文本与生成后端路径一致（api_prefix 正确渲染）

## 8. 实证结论（调研沉淀，防重踩）

1. **copier 内省**：`Template.questions_data` 给全量参数 schema（type/choices/default/when/help），后端 17 参/前端 5 参实测全通；choices 的 disabled 标记（validator 字段）可区分启用/未实现。内部 API，钉 copier 版本 + 隔离在底座钩子
2. **严格渲染**：copier 默认对未声明变量**宽松**（静默渲染空，实测）；`_envops: {undefined: "jinja2.StrictUndefined"}` 可恢复严格（实测硬报错）
3. **无默认必填**：copier.yml 参数不写 default = 必填；`--defaults` 非交互漏传硬报错 `Question "x" is required`（实测）
4. **answers 文件**：模板显式渲染（`[[/{{ _copier_conf.answers_file }}.jinja` + `_envops` 解析文件名），含默认值与 when 激活参数，**不含 `when:false` 派生参数**（实测）
5. **`{% yield %}`**：copier 专属 jinja 扩展（`YieldExtension`），标准 jinja2 不认（实测报 unknown tag）；契约迁 copier 后可用，但契约按约定引用原生触发/原始输入即可
6. **copier 对未声明 `-d` 键静默忽略**（实测退出 0）——桥侧不校验时无感知；检查链 + 契约 StrictUndefined 兜底

## 9. 已知漂移（规划修复，阶段 2 随契约迁移一并处理）

| 位置 | 现状 | 规划修复 |
|---|---|---|
| 契约 §2.1 | 「主应用…无版本前缀」 | 改为渲染 `{{ api_prefix }}`（后端默认 `/api/v1`） |
| 契约 §4.1 | 硬编码 `apiBaseUrl = /api` | 渲染 `{{ api_base_url }}` |
| 契约 §2.6 | child_apps 通用文案 | 引用 `child_apps_raw`（原生），不枚举派生值 |
| 前端 vite proxy | 模板里注释占位，契约描述为已启用 | 契约措辞与模板实际一致，或模板补齐代理 |

## 10. 开放问题（后续处理）

- 契约 copier 模板 envops：标准 `{{ }}`（markdown 无 JSX/Vue 冲突，与现契约一致，建议默认）vs `[[ ]]`——**检查 2 的扫描定界符依赖此决定**：标准 → 扫 `{% if %}`；若选 `[[ ]]` → 扫 `[% if %]`
- `check.py` 通知形式：输出告警 vs 生成对比报告（如 `docs/params-diff.md`）
- `combos/<combo>/` 内除契约外是否含项目 README 模板（现 `project-README.md.jinja` 的归宿）
- **契约模板公共内容复用（推迟）**：多组合时 §1 公共契约/§4 接线等共享章节会在各 CONTRACT.md.jinja 复制——**等新底座组合接入后统一规划**（可考虑 `combos/_common/` + jinja `{% include %}`）
- 桥 `.venv` 依赖：`pyyaml`（读 answers YAML + 组合 copier.yml）+ 内置 `json`；不依赖 copier（只调 CLI）

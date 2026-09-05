# 新底座项目接入指南

把一个**新前端/后端底座**接入 fullstack-bridge 的 `params.json` 对齐协议，分三步：底座侧三件套 → 桥侧登记 → GitHub 配置。

协议现状：**schema v2 两区**——`params` 区（copier 派生、与 copier.yml hash 校验）+ `selection` 区（**可选**，人工策展选择事实，schema 校验、轮转保留，供多端菜单/单端引导）。

## 前置条件

- 底座是 **git 仓库**（桥的 `combos.yaml` version 基线依赖 git，非 git 拒绝）
- 底座模板体在 `template/`（copier.yml 位于其内）
- 已克隆协议仓 `fullstack-param-protocol`（`gen-params.py` + `hooks/pre-commit` + `workflows/params-check.yml`——**接入三件套的单一真源**，复制后不改，避免双源漂移）
- copier **全链钉 `9.17.1`**（协议仓 venv / 底座钩子 `uv run --with 'copier==9.17.1'` / 底座 CI `pip install copier==9.17.1`）：`generated_by` 含 copier patch 版本且参与 verify 比对，任何环境漂版本都会误判

---

## 1. 底座侧接入（三件套，全部从协议仓复制）

```bash
BASE=~/project/<新底座>
PROTO=~/project/fullstack-param-protocol
mkdir -p "$BASE/bin" "$BASE/.githooks" "$BASE/.github/workflows"
```

### 1.1 gen-params.py + 版本标记

```bash
cp "$PROTO/gen-params.py" "$BASE/bin/gen-params.py"
sha256sum "$PROTO/gen-params.py" | awk '{print $1}' > "$BASE/bin/GEN_PARAMS_VERSION"
```

`GEN_PARAMS_VERSION` = vendored 文件内容 sha256；底座 CI 有 **vendor 指纹自检**（`bin/gen-params.py` == 标记），与协议仓漂移在提交即暴露。升级 gen-params.py = 从协议仓复制 + 更新标记。

### 1.2 生成 params.json + 自检

```bash
# 需 copier 环境（钉 9.17.1：uv 临时装或协议仓 .venv）
uv run --with 'copier==9.17.1' python "$BASE/bin/gen-params.py" \
  --template-dir "$BASE/template" --output "$BASE/params.json"
uv run --with 'copier==9.17.1' python "$BASE/bin/gen-params.py" \
  --template-dir "$BASE/template" --output "$BASE/params.json" --verify   # 应通过
```

`params.json`（仓库根）与 copier.yml **一起提交**（原子）。schema 见协议仓 `SCHEMA.md`（两区）。

**（可选）策展 selection 区**——让底座带选择事实，供多端菜单/单端引导消费（不加也合法，只缺选择地基）：

```json
{
  "selection": {
    "suited_for": ["适用场景描述…（自然语言）"],
    "tradeoffs": ["相对同类底座的取舍…"]
  }
}
```

- `suited_for` / `tradeoffs` 都是**字符串数组**；**未知字段容忍并轮转保留**（策展区可演进）
- 手改 params.json 加 selection → 跑一次 gen-params（pre-commit 会做）归一格式；**不触发 copier 过期**（selection 不参与 hash）
- 底座 CI 只对 selection 做 **schema 校验**（非 list[str] → 失败）

### 1.3 pre-commit 钩子（best-effort 生成）

```bash
cp "$PROTO/hooks/pre-commit" "$BASE/.githooks/pre-commit"
chmod +x "$BASE/.githooks/pre-commit"
git -C "$BASE" config core.hooksPath .githooks
```

钩子行为：提交时 best-effort 重生成 params.json（钉 copier 9.17.1），**不拦截**（硬门槛在 CI）。解析器主路径 `uv run --with 'copier==9.17.1'`；**兜底工具 python 须同为 9.17.1**，非钉版本跳过并提示（防静默改写 `generated_by`）。仓库根推导 CWD 无关。

### 1.4 CI workflow（params-check.yml）

```bash
cp "$PROTO/workflows/params-check.yml" "$BASE/.github/workflows/params-check.yml"
```

workflow 双职责（内容见现有底座，verify job 内含 vendor 指纹自检）：

```yaml
jobs:
  verify:                       # 硬门槛，失败阻止合并
    steps:
      - run: pip install copier==9.17.1        # 钉 copier 版本（与协议仓/钩子统一）
      - run: |                                # vendor 指纹自检（与协议仓同源）
          test "$(sha256sum bin/gen-params.py | cut -d' ' -f1)" = "$(cat bin/GEN_PARAMS_VERSION)"
      - run: python bin/gen-params.py --template-dir template --output params.json --verify
                                            # 双区自检：params↔copier.yml hash + selection schema
  notify-drift:                   # 软信号：params.json 变化 → dispatch 桥 check-drift
    if: github.ref == 'refs/heads/main' && github.event_name == 'push' && vars.DRIFT_DISPATCH_ENABLED == 'true'
    # 探测 params.json 变化 → workflow_dispatch fullstack-bridge check-drift（ref: main）
    # 载荷: base_repo=<仓库名> base_version=<commit sha>
```

---

## 2. 桥侧登记

### 2.1 combos.yaml

打开 `fullstack-bridge/combos.yaml`：

- **注册底座 git 地址**：`bases:` 注册表加 `<底座名>: <git 地址>`（可执行文件克隆底座 / CI clone-bases 用）
- **并入现有组合**（如新后端配 react）：改对应 combo 的 frontend/backend `source` + `version`
- **全新组合**：加一个 combo 条目：

```yaml
bases:
  vite-react-spa-template:   https://github.com/jianghua-developer/vite-react-spa-template.git
  python-fastapi-template:   https://github.com/jianghua-developer/python-fastapi-template.git

combos:
  python-react:            # 例：加 python-vue 时复制并改名
    units:                          # key = 生成目录名；每项 {source, version, app, stack}
      frontend:
        source: <底座名>             # 系列底座名 → bases 注册表 git URL（clone 到缓存）
        version: <刚推送的 commit>    # 对齐基线（手动维护；含底座 selection 的新内容也随 bump 带上）
        app:   "前端应用"            # README 职责描述（目录表用）
        stack: "..."                # 技术栈（README 渲染用）
      backend:
        source: <底座名>
        version: <刚推送的 commit>
        app:   "后端服务"
        stack: "..."
    edges: [[frontend, backend]]    # 有序对 [consumer, provider]，provider 契约属主
    selection:                      # （可选）combo 段：只放**组合不可约**事实
      suited_for:                   #   ——技术栈事实单一真源在各底座 params.json selection 区，禁止重复写
        - "前后端分离一体交付：<前端> + <后端> 同仓，CONTRACT 契约随生成自动对齐"
      tradeoffs:
        - "相对单端分别生成再手工对接：契约/联调前置进生成链（桥治理）"
```

> 桥管**多单元组合**（N≥2，units+edges）；单模板形态（纯前端/纯后端/CLI）不在桥，走能力层 `generate_single`（后续）。
> source 须为 bases 注册裸名；多端只认注册组合（Q4）。底座一律 clone 到缓存（`~/.cache/fullstack-bridge/bases`）。
> 每个 unit 需给 `app`（职责描述）+ `stack`（技术栈）——README 目录/技术栈表按 units 循环渲染。
> combo 段 `selection` 字段仅 `suited_for`/`tradeoffs`（`list[str]`）；未知字段/非数组 → 结构校验拒绝（check 入口整注册表 / generate 单目标）。

**version 语义**：组合已复核/对齐到的底座 git 版本，手动维护。底座**加了 selection/内容**（params 区未变）→ bump 即可，契约不受影响；底座 **params 区变了** → bump 后必须过 `check` 对齐契约，必要时改 `combos/<组合>/`。

### 2.2 契约模板（全新组合时）

新建 `combos/<组合>/` 目录：`copier.yml`（全必填零默认 + `_envops` StrictUndefined，声明契约引用的参数）+ `CONTRACT.md.jinja`。参考 `combos/python-react/`。

契约可引用底座**派生参数**（如 `child_apps` 用 `{% for %}` 枚举）；`{% yield %}` 仅限文件名。

### 2.3 桥侧验证

```bash
cd ~/project/fullstack-bridge
uv run cli.py check --combo <组合>        # 结构门（入口整注册表）+ 对齐
uv run cli.py check --all
uv run cli.py list-combos --json          # 菜单：units/edges + 合并 selection（底座并集 + combo 段）
uv run cli.py show-combo <组合> --json    # 参数基线（原生可问 / internal / 派生只读）+ 合并 selection
```

> `list-combos` / `show-combo`（`--json`）是能力层（bridge-mcp-server）纯 cli 消费的多端内省面——新底座接入后应在此确认菜单出现、selection 合并、参数基线正确。

---

## 3. GitHub 配置（激活 notify-drift 自动链路）

### 3.1 建 PAT（一次，若未建）

- GitHub → Settings → Developer settings → **Personal access tokens → Tokens (classic) → Generate**
- Note：`fullstack-bridge-dispatch`；Expiration：合理期限
- **勾选 `workflow` scope**（触发 Actions 必需）
- 生成后**立即复制**（只显示一次）
- 或 Fine-grained：Repository access 选 `fullstack-bridge`，Actions: **Read and write**

> token 只需对 **fullstack-bridge** 有 workflow 权限（用于触发桥仓 check-drift），不需要对新底座仓有权限。

### 3.2 新底座仓库加 Secret

新底座 GitHub 仓库 → **Settings → Secrets and variables → Actions → Secrets → New repository secret**：

| 项 | 值 |
|---|---|
| Name | `BRIDGE_DISPATCH_TOKEN` |
| Secret | 3.1 的 PAT |

### 3.3 新底座仓库加 Variable

同一页面 → **Variables → New repository variable**：

| 项 | 值 |
|---|---|
| Name | `DRIFT_DISPATCH_ENABLED` |
| Value | `true` |

> **Secret 与 Variable 成对配置**：Variable 门控 notify-drift job；dispatch 用 Secret 当 token。只开 Variable 不设 Secret → dispatch 步骤空 token 报红。

### 3.4 提交推送

新底座：params.json（含 selection 若策展）+ 三件套一起 commit + push main；桥：combos.yaml（含可选 combo 段 selection）/ 契约模板 commit + push main。

---

## 4. 验证

1. **桥侧**：`uv run cli.py list-combos --json` / `show-combo <组合> --json` → 新底座出现在菜单、selection/参数正确
2. **桥侧**：手动触发 `fullstack-bridge` → Actions → check-drift → Run workflow（填 `base_repo` / `base_version`）→ 应产出报告
3. **真实链路**：改新底座 copier.yml → push main → params-check verify（双区）过 → notify-drift dispatch → 桥 check-drift 开 issue
4. `uv run cli.py check --all` 应全部对齐

## 触发链路回顾

```
底座 params.json 变化 → base CI verify(双区自检, 阻止) → notify-drift(Variable=true)
  → dispatch 桥 check-drift(Secret 作 token) → cli.py check 对比 combos.yaml 基线
  → 未对齐开 issue → 人/AI 改 combos/<组合>/ + 手动 bump combos.yaml version → 桥 CI 门槛 → 对齐
```

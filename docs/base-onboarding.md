# 新底座项目接入指南

把一个**新前端/后端底座**接入 fullstack-bridge 的 `params.json` 对齐协议，分三步：底座侧三件套 → 桥侧登记 → GitHub 配置。

## 前置条件

- 底座是 **git 仓库**（桥的 `combos.yaml` version 基线依赖 git，非 git 拒绝）
- 底座模板体在 `template/`（copier.yml 位于其内）
- 已克隆协议仓 `fullstack-param-protocol`（含 `gen-params.py`）
- 已有一个接好的底座可作参考复制源（本文以现有底座为 `SRC_BASE`）

---

## 1. 底座侧接入（三件套）

### 1.1 vendored gen-params.py + 版本标记

```bash
SRC_BASE=~/project/vite-react-spa-template   # 参考底座
BASE=~/project/<新底座>
PROTO=~/project/fullstack-param-protocol

mkdir -p "$BASE/bin" "$BASE/.githooks" "$BASE/.github/workflows"
cp "$PROTO/gen-params.py" "$BASE/bin/gen-params.py"
sha256sum "$PROTO/gen-params.py" | awk '{print $1}' > "$BASE/bin/GEN_PARAMS_VERSION"
```

### 1.2 生成 params.json + 自检

```bash
# 需 copier 环境（uv 临时装或协议仓 .venv）
uv run --with copier python "$BASE/bin/gen-params.py" \
  --template-dir "$BASE/template" --output "$BASE/params.json"
uv run --with copier python "$BASE/bin/gen-params.py" \
  --template-dir "$BASE/template" --output "$BASE/params.json" --verify   # 应通过
```

`params.json`（仓库根）与 copier.yml **一起提交**（原子）。schema 见协议仓 `SCHEMA.md`。

### 1.3 pre-commit 钩子（best-effort 生成）

```bash
cp "$SRC_BASE/.githooks/pre-commit" "$BASE/.githooks/pre-commit"
chmod +x "$BASE/.githooks/pre-commit"
git -C "$BASE" config core.hooksPath .githooks
```

钩子行为：提交时 best-effort 重生成 params.json，**不拦截**（硬门槛在 CI）。脚本内容可从现有底座 `.githooks/pre-commit` 复制（copier 环境解析器 + CWD 无关的仓库根推导）。

### 1.4 CI workflow（params-check.yml）

```bash
cp "$SRC_BASE/.github/workflows/params-check.yml" "$BASE/.github/workflows/params-check.yml"
```

workflow 双职责（内容见现有底座）：

```yaml
# ① verify：params.json == copier.yml 自检（失败阻止合并）
jobs:
  verify:
    steps:
      - run: pip install copier==9.17.0   # 钉 copier 版本
      - run: python bin/gen-params.py --template-dir template --output params.json --verify
  # ② notify-drift：params.json 变化 → dispatch 桥 check-drift（软信号）
  notify-drift:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push' && vars.DRIFT_DISPATCH_ENABLED == 'true'
    steps:
      # 探测 params.json 变化 → workflow_dispatch fullstack-bridge check-drift（ref: main）
      # 载荷: base_repo=<仓库名> base_version=<commit sha>
```

---

## 2. 桥侧登记

### 2.1 combos.yaml

打开 `fullstack-bridge/combos.yaml`：

- **并入现有组合**（如新后端配 react）：改对应 combo 的 frontend/backend `source` + `version`
- **全新组合**：加一个 combo 条目：

```yaml
combos:
  python-react:            # 例：加 python-vue 时复制并改名
    frontend:
      source:  <底座名>          # 系列底座名 → ../<底座名>/template（须 git 仓）；或 git 地址
      version: <刚推送的 commit>  # 对齐基线（手动维护）
    backend:
      source:  <底座名>
      version: <刚推送的 commit>
    contract: <组合名>
    stack:                        # 技术栈元数据（README 渲染用）
      frontend_app:    "..."
      backend_app:     "..."
      frontend_stack:  "..."
      backend_stack:   "..."
```

### 2.2 契约模板（全新组合时）

新建 `combos/<组合>/` 目录：`copier.yml`（全必填零默认 + `_envops` StrictUndefined，声明契约引用的参数）+ `CONTRACT.md.jinja`。参考 `combos/python-react/`。

契约可引用底座**派生参数**（如 `child_apps` 用 `{% for %}` 枚举）；`{% yield %}` 仅限文件名。

### 2.3 桥侧验证

```bash
cd ~/project/fullstack-bridge
uv run check.py --combo <组合>     # 应全部对齐
uv run check.py --all
```

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

新底座：params.json + 三件套一起 commit + push main；桥：combos.yaml / 契约模板 commit + push main。

---

## 4. 验证

1. **桥侧**：手动触发 `fullstack-bridge` → Actions → check-drift → Run workflow（填 `base_repo` / `base_version`）→ 应产出报告
2. **真实链路**：改新底座 copier.yml → push main → params-check 的 verify 过 → notify-drift dispatch → 桥 check-drift 开 issue
3. `uv run check.py --all` 应全部对齐

## 触发链路回顾

```
底座 params.json 变化 → base CI verify(自检, 阻止) → notify-drift(Variable=true)
  → dispatch 桥 check-drift(Secret 作 token) → check.py 对比 combos.yaml 基线
  → 未对齐开 issue → 人/AI 改 combos/<组合>/ + 手动 bump combos.yaml version → 桥 CI 门槛 → 对齐
```

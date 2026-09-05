# fullstack-bridge · 前后端连通层

把**单端模板**与**组合契约**整合为一个「前后端一体」项目目录，供 AI 生成完整业务系统时，前后端实现共同对照同一份契约。**全 copier 工具链**（各端/契约/README 均 copier 渲染）。

## 定位

- 单端模板（`vite-react-spa-template` / `python-fastapi-template` …）只约束单端机制与写法
- 本目录约束**多端怎么对上**：组合契约 + 整合编排 + 对齐检查（多单元组合，N≥2）
- 选定技术栈后，一条命令生成大目录：

```text
my-app/
├── frontend/          # 单元 frontend（目录名 = combos.yaml units key）
├── backend/           # 单元 backend
├── docs/CONTRACT.md   # 裁剪后的契约（按实际生成参数渲染，确定性）
└── README.md          # 消费方视角入口
```

## 结构

| 文件/目录 | 职责 |
|---|---|
| `cli.py` | 统一 CLI（Click）：`generate <combo> <project>` + `check`，选项由底座 params.json 数据驱动 |
| `bridge/` | 共享库包：`combos.py`（units/edges 解析 + 底座统一 clone + param_schema）、`copier.py`（执行）、`answers.py`（剔除合并） |
| `combos.yaml` | 多端治理真源：`bases` 注册表 + `combos`（units≥2 + edges + version 基线 + units.{key}.{app,stack} README 元数据） |
| `combos/<组合>/` | 契约 copier 模板（`copier.yml` 全必填零默认 + `CONTRACT.md.jinja`，可用派生参数枚举） |
| `templates/project-README/` | 项目 README copier 模板（cli.py 从 combos.yaml `units.{key}.{app,stack}` 装配 `units_desc` 注入渲染） |
| `.github/scripts/clone-bases.py` | 统一底座获取：克隆到缓存（CI 预克隆 + 打包烘焙 params.json） |
| `.github/workflows/` | `check-drift`（收底座信号）+ `bridge-gate`（改 combos 时校验）+ `build-executable` |

## 快速开始

```bash
# generate：组合子命令，选项 = 该组合 units 的 params.json schema（--help 可见）
uv run python cli.py generate python-react my-app \
  --project-description "业务描述" --auth-mode opaque --with-db true --with-child-app true \
  --child-apps-raw "backend,admin:adm"

# check：对齐检查
uv run python cli.py check --combo python-react
```

- 底座**一律 clone 到缓存**（`~/.cache/fullstack-bridge/bases`，按 combos.yaml version checkout）——无源码兄弟目录模式；首次需网络，之后缓存复用。
- 选项名 = 底座**原生参数名**（`--child-apps-raw`），派生参数（`child_apps`）由 copier 计算不暴露。
- 依赖由底座 `_tasks` 自动安装（前端 pnpm install / 后端 uv sync）；`--skip-tasks` 跳过（测试用）。
- 可执行文件（`dist/bridge`）内烘焙各底座 params.json——`--help`/schema 零网络。

## 组合映射（combos.yaml）

```yaml
combos:
  python-react:
    units:                                  # key = 生成目录名（frontend/ backend/…）
      frontend:
        source: vite-react-spa-template     # 底座名 → bases 注册表 git URL（clone 到缓存）
        version: <git-ref>                  # 该组合已复核/对齐到的底座版本（check 基线）
        app:   "前端应用"                    # README 职责描述（目录表用）
        stack: "Vite + React + TypeScript + TanStack Query + axios"   # 技术栈（README 用）
      backend:
        source: python-fastapi-template
        version: <git-ref>
        app:   "后端服务"
        stack: "FastAPI + SQLAlchemy（async）+ pydantic-settings"
    edges: [[frontend, backend]]            # 有序对 [consumer, provider]，provider 契约属主
```

加新组合 = combos.yaml 加 `units`(≥2)+`edges` + 新建 `combos/<组合>/` 契约模板目录，`cli.py`/`bridge/` 零改动（CLI 选项由 params.json schema 自动生成）。**新底座/新组合接入的完整操作手册（含 GitHub 配置步骤）见 [docs/base-onboarding.md](docs/base-onboarding.md)。**

## 契约模板约定

- 目录 `combos/<组合>/`：`copier.yml`（**全必填零默认** + `_envops` StrictUndefined）+ `CONTRACT.md.jinja`
- 条件用各单元共享的原生 copier 参数名（auth_mode / with_db / with_child_app / api_prefix…）；布尔条件直接 `{% if with_db %}`（copier 类型强转，无 `== 'true'` 字符串坑）
- **可用派生参数**（`when:false` 由 copier 计算，如 `child_apps`，由 `child_apps_raw` 输入）——`{% for child in child_apps %}` 枚举子应用（`{% yield %}` 仅限文件名）
- 渲染数据 = 生成后各单元 `.copier-answers.yml` 的**实际生效值**（含 copier 默认）剔除合并——默认漂移在构造上不存在
- **合并 = per-edge 属主**：沿 edges（consumer→provider），provider 为属主、同名 provider 赢；用户显式参数最高（python-react 单 edge ≡ 用户 > 后端 > 前端）
- 生成链：`cli.py generate` 生成各单元 → 读 answers → 按 edges 剔除合并 → 喂契约 copier 模板

## 共享参数作用域（何时全链路共享 / 何时锁定单 edge）

跨多 unit 的同名参数（如 `auth_mode`）在 CLI/schema 中合并为**一个共享参数**。它的作用域由**语义**决定，而非命名巧合：

| 情形 | 作用域 | 例子 |
|---|---|---|
| 该参数在整条链是**同一决策**，各端裁剪实现它 | **全链路共享**——单值广播到所有声明它的端，契约以此单值渲染 | `auth_mode`：python-react 双端都是「要不要 opaque 会话」这一个决策 |
| 该参数只在**某条 edge 的两端**有语义，其它端无关 | 自然落在该 edge / 相关 unit，其它 unit 不声明即不受影响 | `api_base_url`（前端调 BFF）、`api_prefix`（后端），各端私有 |
| 相邻 edge 上本可**不同取值**（如 UI↔BFF 用 opaque、BFF↔真后端用 jwt） | **锁定为各 edge / unit 的私有参数**——不把它们当「同一共享参数」试图分段 | BFF 底座自行声明 `upstream_auth` 表达对上游策略 |

**设计约束（U1 定案）**：**不引入逐端参数命名空间**（如把共享的 `auth_mode` 拆成 `ui.auth_mode / bff.auth_mode / api.auth_mode`）。「分段认证」这类诉求不是「同一参数需分段取值」，而是「该参数本就不属于共享语义」——应表达为对应 edge/unit 的**私有参数**，由逐跳契约各自承载。后果：一个 combo 里共享参数越少、各 edge 语义越独立，越该用私有参数 + 多 edge 契约（ui-bff-api 形态）表达；反之共享参数多 = 全链强耦合的单一契约。`cli.py`/能力层的共享参数标 `shared: true`，agent 填一个值即广播，不能也不需分端指定。

## 对齐协议（params.json）

各底座根目录 `params.json`（协议仓 `fullstack-param-protocol` 的 `gen-params.py` 经 copier 内省生成、底座自维护）。`cli.py check` 据此检测底座漂移、校验组合对齐（选项 schema 亦由 params.json 驱动），未对齐经 `check-drift` workflow 开 issue。

## 依赖

| 项 | 说明 |
|---|---|
| 底座/契约/README 生成 | `copier`（系列底座 + 组合模板，Python API） |
| CLI | `click`（统一入口，选项数据驱动） |
| 桥脚本 | Python 3 + `pyyaml` + `click`（依赖声明在 `pyproject.toml`，uv 管理） |

```bash
# 重建桥环境（按 pyproject.toml）
uv sync
```

## 测试

```bash
uv sync --dev        # 装 pytest（dev 依赖组）
uv run pytest        # 单元测试（bridge 各模块/CLI）+ e2e（cli.py generate 生成校验）
```

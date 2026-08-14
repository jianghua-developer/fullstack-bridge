# fullstack-bridge · 前后端连通层

把**单端模板**与**组合契约**整合为一个「前后端一体」项目目录，供 AI 生成完整业务系统时，前后端实现共同对照同一份契约。**全 copier 工具链**（前端/后端/契约/README 均 copier 渲染）。

## 定位

- 单端模板（`vite-react-spa-template` / `python-fastapi-template` …）只约束单端机制与写法
- 本目录约束**两端怎么对上**：组合契约 + 整合编排 + 对齐检查
- 选定技术栈后，一条命令生成大目录：

```text
my-app/
├── frontend/          # 前端应用
├── backend/           # 后端服务
├── docs/CONTRACT.md   # 裁剪后的契约（按实际生成参数渲染，确定性）
└── README.md          # 消费方视角入口
```

## 结构

| 文件/目录 | 职责 |
|---|---|
| `integrate.py` | 整合编排（CLI + 生成链，全 copier） |
| `bridge/` | 共享库包：`combos.py`（组合解析/git 校验）、`copier.py`（执行）、`answers.py`（剔除合并） |
| `combos.yaml` | 组合映射（缩写 → 前端/后端 source + version 基线 + 契约模板 + stack 技术栈） |
| `combos/<组合>/` | 契约 copier 模板（`copier.yml` 全必填零默认 + `CONTRACT.md.jinja`，可用派生参数枚举） |
| `check.py` | 检查链（检查 1：pinned 漂移/子集；检查 2：契约取值覆盖；未对齐告警） |
| `templates/project-README/` | 项目 README copier 模板（技术栈来自 combos.yaml stack） |
| `.github/workflows/` | `check-drift`（收底座信号）+ `bridge-gate`（改 combos 时校验） |

## 快速开始

```bash
# 模式 A：组合缩写
.venv/bin/python integrate.py python-react my-app \
  --description "业务描述" --auth-mode opaque --with-db true --with-child-app true

# 模式 B：显式模板（--frontend/--backend 互斥于缩写、必须成对）
.venv/bin/python integrate.py my-app \
  --frontend ../vite-react-spa-template/template --backend ../python-fastapi-template/template

# 任意底座参数：-D key=value 通用透传（零桥改动，见 combos.yaml）
# 依赖由生成器自动安装（前端 pnpm install / 后端 uv sync）
```

两种模式**互斥**：缩写与 `--frontend/--backend` 不可同时出现；`--frontend/--backend` 必须成对。

**底座必须 git 仓**：本地目录须为 git 检出（检查链依赖 `params.json` version 基线），非 git 直接拒绝。模式 B 是**逃生舱**——治理（check）属于 combos.yaml 注册的组合。**模式 B 的 `--frontend/--backend` 须是注册组合的本地解析路径**（与 combos.yaml 裸名解析一致）；**git 地址匹配不上注册组合 → 不提供契约**（报「未注册组合」，不生成）。

## 组合映射（combos.yaml）

```yaml
combos:
  python-react:
    frontend:
      source:  vite-react-spa-template   # 系列底座名 → ../<name>/template（须 git 仓）；或 git 地址
      version: <git-ref>                  # 该组合已复核/对齐到的底座版本（check 基线）
    backend:
      source:  python-fastapi-template
      version: <git-ref>
    contract: python-react
    stack:                                # 技术栈元数据（README 渲染用）
      frontend_app:    "Vite + React + TypeScript"
      backend_app:     "FastAPI"
      frontend_stack:  "Vite + React + TypeScript + TanStack Query + axios"
      backend_stack:   "FastAPI + SQLAlchemy（async）+ pydantic-settings"
```

加新组合 = 这里加一行 + 新建 `combos/<组合>/` 契约模板目录，`integrate.py`/`check.py` 零改动。

## 契约模板约定

- 目录 `combos/{后端}-{前端}/`：`copier.yml`（**全必填零默认** + `_envops` StrictUndefined）+ `CONTRACT.md.jinja`
- 条件用**后端 copier 参数名**（auth_mode / with_db / with_child_app / api_prefix…）；布尔条件直接 `{% if with_db %}`（copier 类型强转，无 `== 'true'` 字符串坑）
- **可用派生参数**（`when:false` 由 copier 计算，如 `child_apps`）——`{% for child in child_apps %}` 枚举子应用（`{% yield %}` 仅限文件名）
- 渲染数据 = 生成后两端 `.copier-answers.yml` 的**实际生效值**（含 copier 默认）剔除合并——默认漂移在构造上不存在
- **合并优先级：用户参数 > 后端 answers > 前端 answers**（同名后端覆盖前端，契约以后端为主）
- 生成链：`integrate.py` 读两端 answers → 剔除合并 → `-d` 喂契约 copier 模板

## 对齐协议（params.json）

各底座根目录 `params.json`（协议仓 `fullstack-param-protocol` 的 `gen-params.py` 经 copier 内省生成、底座自维护）。`check.py` 据此检测底座漂移、校验组合对齐，未对齐经 `check-drift` workflow 开 issue。

## 依赖

| 项 | 说明 |
|---|---|
| 前端/后端生成 | `copier`（系列底座模板，CLI） |
| 契约/README 渲染 | `copier`（组合模板，CLI） |
| 桥脚本 | Python 3 + `pyyaml`（依赖声明在 `pyproject.toml`，uv 管理） |

```bash
# 重建桥环境（按 pyproject.toml）
uv sync
```

## 测试

```bash
uv sync --dev        # 装 pytest（dev 依赖组）
uv run pytest        # 单元测试（bridge 各模块/CLI）+ e2e（integrate.py 生成校验）
```

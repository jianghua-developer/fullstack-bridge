# fullstack-bridge · 前后端连通层

把**单端模板**与**组合契约**整合为一个「前后端一体」项目目录，供 AI 生成完整业务系统时，前后端实现共同对照同一份契约。

## 定位

- 单端模板（`vite-react-spa-template` / `python-fastapi-template` …）只约束单端机制与写法
- 本目录约束**两端怎么对上**：组合契约 + 整合编排
- 选定技术栈后，一条命令生成大目录：

```text
my-app/
├── frontend/          # 前端应用
├── backend/           # 后端服务
├── docs/CONTRACT.md   # 裁剪后的契约（按参数渲染，确定性）
└── README.md          # 消费方视角入口
```

## 组合索引

| 组合 | 契约模板 | 前端模板 | 后端模板 |
| --- | --- | --- | --- |
| python-react | `python-react.md.jinja` | `vite-react-spa-template` | `python-fastapi-template` |

> 新增组合 = `bin/integrate.sh` 组合映射加一行 + 新建 `{后端}-{前端}.jinja`。渲染器 `bin/render.py` 通用，无需改。

## 快速开始

```bash
# 1. 生成项目（参数同时驱动后端模板与契约渲染，保证两端一致）
bin/integrate.sh python-react my-app \
  --description "业务描述" --api-base-url /api \
  --auth-mode opaque --with-db true --with-redis true --with-child-app true

# 2. 安装依赖（脚本已跳过，生成后统一装）
cd my-app/frontend && pnpm install
cd my-app/backend && uv sync
```

## 契约模板约定

- 文件名 `{后端}-{前端}.jinja`；条件块用**后端 copier 参数名**（auth_mode / with_db / with_redis / with_child_app），渲染后无残留
- 渲染：`bin/render.py`（python3 + jinja2）；未定义变量即报错，防静默漏渲染
- 契约按端分：公共契约（两端共守）/ 后端侧 / 前端侧（引用前端 docs）/ 开发接线

## 依赖

| 项 | 说明 |
| --- | --- |
| 前端生成 | `copier`（前端模板 `../vite-react-spa-template/template`，已迁移 copier） |
| 后端生成 | `copier`（本机已装，`../python-fastapi-template/template`） |
| 契约渲染 | python3 + jinja2（`fullstack-bridge/.venv`） |

```bash
# 重建渲染环境（若 .venv 缺失）
uv venv .venv
uv pip install --python .venv/bin/python jinja2
```

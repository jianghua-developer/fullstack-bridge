# 生成能力重构 · 步骤化改动设计

> 分支：refactor/nunit-topology ｜ 上游：[docs/generation-architecture.md](generation-architecture.md)（Q1–Q4 已定案）
> **本轮范围（已定案，2026-09-03 扩定）**：
> ① 代码支持多 units 模式（N≥2、含多 edge）；
> ② CLI 全量迁 **Click**——integrate + check 统一多命令入口，删 `-D`/精选别名，选项 schema 由**底座 params.json** 数据驱动；
> ③ **砍本地模式**——底座一律 clone/baked（钉 combos.yaml version）；源码走缓存 clone，可执行另烘焙 params.json（§1.4）；
> ④ 文档同步：桥仓根 README.md + docs/base-onboarding.md。
> **不在本轮**：新底座接入、契约多 edge 目录、`templates/project-README/` 通用化、bridge-mcp-server 一切（见 §4）。
> **回归护栏**：python-react 组合 e2e 全程保持绿（生成结构不变）；schema 从钉 version 的 params.json 读。

---

## 0. 本轮边界（精确）

**做**（按依赖序）：
1. **运行形态统一（clone/baked）**——combos.py 去源码兄弟目录分支，唯一底座获取路径 = clone 到缓存 + checkout combos.yaml version；
2. **数据模型 units/edges**——combos.yaml 迁移 + 访问器（python-react 单 edge 回归）；
3. **CLI 全量 Click 重构**——统一入口（integrate + check 子命令），per-combo 子命令选项 = params.json 数据驱动，删 `-D`/别名；
4. **check.py 逻辑沿 units/edges**；
5. **可执行 params.json 烘焙**——frozen 模式 schema/help 零网络（见 §1.4）；
6. 文档（README / onboarding）。

**不做**：
- 不接入任何新底座（nuxt-fullstack / bff-gateway / cli）；
- 不改契约多 edge 目录（`docs/contracts/`）——python-react 单 edge 维持 `docs/CONTRACT.md`；
- 不改 bridge-mcp-server 任何文件；
- 不改 `templates/project-README/`。

---

## 1. 运行形态统一：砍本地模式，一律 clone/baked

### 背景（为何砍）
源码模式读 `../<底座>/template` 兄弟目录 HEAD，version 被忽略 → 生成/schema 读「开发者机器碰巧 checkout 的 HEAD」，与治理基线错位，schema 不确定。真实情况 = 桥消费**钉 version 的底座快照**。

### 改动

#### 1.1 bridge/combos.py：唯一底座获取路径

```python
# 删除源码兄弟目录分支：resolve_template / resolve_base / ensure_git_repo 不再用 BRIDGE.parent / source
# 统一：clone 到缓存 → checkout combos.yaml version → 返回 template/（或仓库根给 check）
def _ensure_base(source, version) -> Path:
    # clone 到 _BASE_CACHE/<source>（已存在跳过）→ checkout version → 返回仓库根
def resolve_template(source, version) -> str:   # = _ensure_base(...) / "template"
def resolve_base(source, version) -> Path:      # = _ensure_base(...)   （check 读 params.json 用）
def ensure_git_repo(source):                    # 不变量：底座必 git（clone 所得天然是），删除兄弟目录检查
```

- `_FROZEN` 分支消失（源码/可执行同路径）；`_frozen_base` 并入 `_ensure_base`。
- 显式本地路径/git URL 仍原样（dev/逃生保留，但**裸名 = 一律 clone**，不再映射兄弟目录）。
- `is_url` 判断保留。
- **params.json 从缓存 clone 读**（钉 version 后 checkout，天然对齐）。

#### 1.2 `.github/scripts/clone-bases.py`：目标改缓存目录（CI 预克隆保留）

- `dest = BRIDGE.parent / src` → `dest = <缓存>/src`（与 combos.py `_BASE_CACHE` 一致，导出共享常量）；
- 逻辑不变（--all / --for-base 沿 units，见 §2.5）；check-drift CI 显式先 clone-bases 再 check。

#### 1.3 影响：开发/测试行为变化
- 底座开发循环：改底座 → commit+push → bump combos.yaml version → 桥 clone 验证（原本地即时反馈消失，已接受）；
- 首次生成/测试需拉底座（网络），之后 `~/.cache/fullstack-bridge/bases` 复用；
- 测试不再依赖兄弟目录存在。

#### 1.4 可执行 params.json 烘焙（frozen 模式 schema 零网络）

**边界（防误设计）**：烘焙 ≠ 免除生成时的 clone。底座 `template/`（copier copy 用）与 check 的版本对比（`git show <sha>:params.json`）仍需 clone；烘焙只消除 **schema/选项注册/`--help`** 对底座的网络依赖——frozen 下 `param_schema` 读烘焙快照，不必为出 help 先拉 git。

- params.json 位于底座**仓库根**（非 `template/` 内）——打包时需从「钉 version 的缓存 clone」或该 version 的仓库中取；
- **integrate.spec datas 增补**：为每个 combos.yaml units 引用的底座 source，取其 params.json → 打进包内（如 `bases_params/<source>.json`）；打哪个 version = 打包时刻 combos.yaml 钉的 version（随包冻结）；
- 打包前提 = 本地已 clone 该底座到 `_BASE_CACHE`（`uv run pyinstaller` 前先 `clone-bases.py --all`，CI 亦然）；
- `bridge/combos.py`：`param_schema` 读参分流——frozen 读 `sys._MEIPASS/bases_params/<source>.json`；源码读缓存 clone 的 params.json；
- 选型：本轮源码模式仍走缓存 clone 读 params.json（首拉一次），frozen 走烘焙；两者读的都是同一「钉 version」内容。

---

## 2. 数据模型 + 生成链（units/edges）

### 2.1 combos.yaml：python-react 迁移 units/edges

```yaml
combos:
  python-react:
    units:                                  # 每项 {source, version}
      frontend: { source: vite-react-spa-template, version: 0034ec9 }
      backend:  { source: python-fastapi-template, version: c73aa7b }
    edges: [[frontend, backend]]            # 有序对 [consumer, provider]；provider 契约属主
    stack: { ... }                          # 不变
```

- **去 `contract:` 字段**，契约目录固定 = combos/\<combo\>（④ 定案）；
- `edges` **必填显式**，有序对列表，**支持多 edge**（③ 定案）；
- `bases:` 段不变；**不做旧格式兜底**（⑥ 定案）。

### 2.2 bridge/combos.py：units/edges 访问器

```python
def iter_units(combo)         # -> [(key, {source, version})]，按声明序
def iter_unit_sources(combo)  # -> [source, ...]
def edge_pairs(combo)         # -> [(consumer_key, provider_key), ...]；校验 key ∈ units，否则 SystemExit
def merge_order(combo)        # edges 展平：consumer→provider 序（含中间单元去重）→ 合并序
```

- `declared_params(combo)`（combos/\<combo\>/copier.yml）逻辑不变。

### 2.3 参数 schema 源：各 unit params.json（derive，不抄清单）

- 本轮定案：**共享/私有参数不手抄进 combos.yaml**；schema 全部来自各 unit 底座 params.json 并集；
- `param_schema(combo)`：遍历 units 读 params.json → 并集 → **暴露全部 `derived:false` 原生参数**（含派生参数的**输入**——如 `child_apps_raw` 本身是原生、会暴露，用户填它、copier 才算 `child_apps`）；**仅 `derived:true` 纯派生值不暴露**（由 copier 计算）→ 跨 unit 同名合并为共享（去重成一个选项）→ 返回结构化 schema（type/choices/default/derived）。

### 2.4 integrate 生成链

- `ComboPlan`：`name / units[(key,src,version)] / edges / contract_dir / stack / schema`；
- `generate(plan, project_dir, project_name, user_params, skip_tasks)`：遍历 units → clone 底座（§1.1）→ copier → 按 key 收集 answers → 合并 → 契约/README（同现）；
- 合并 = `merge_order(combo)` + user_params 最高 + project_name 强制原始名；多 edge 单测覆盖。

### 2.5 check.py：沿 units/edges + schema 源 params.json

- `_check_drift` / `_union_params`：沿 `iter_units`；`resolve_base(src, version)` 读缓存 clone 的 params.json；
- `select_targets`：命中任一 unit source 入选；
- `_check_subset/_check_coverage`：契约声明（declared_params）与 params.json 并集对比，逻辑沿用。

### 2.6 `.github/scripts/clone-bases.py`：双端遍历 → 沿 units（叠加 §1.2 改缓存目标）

---

## 3. CLI 全量 Click 重构（统一入口 + 数据驱动 schema + 删 -D/别名）

### 3.1 目标形态

```
bridge                              # 顶层 Click group
├─ generate <combo> <project>       # 每 combo 一个子命令（add_command 循环建）
│     选项 = 该 combo schema（add_argument 循环注）→ <project> 为位置参数（保留，定案）
└─ check [--combo | --all | --base-repo --base-version]
# integrate + check 统一单入口
```

- **Click（非 Typer）**——动态选项原生 + agent-first 下 Typer UI 溢价不值（定案）。
- 统一多命令入口（原「Typer 触发点①」以 Click 形态落地）；check 一起迁（定案）。

### 3.2 per-combo 子命令 + 选项 schema（核心机制，定案形态）

- 形态 = **顶层 `click.Group` + 循环 `add_command`（每 combo 一 command）+ 循环 `add_argument`（每选项）**——即偏好方案（等价 add_typer + click.Group + 循环 add_argument，纯 Click 无 Typer 层）：

```python
group = click.Group()
for combo in load_combos():
    cmd = click.Command(name=combo, params=[project_arg])
    for p in param_schema(combo):           # §2.3，读钉 version 的 params.json
        cmd.params.append(click.Option([f"--{p.name}"], type=p.type,
                                        default=p.default, help=p.help,
                                        **p.choice_kwargs))
    group.add_command(cmd)
```

- `param_schema(combo)`（§2.3）：读各 unit params.json 并集 → **暴露 `derived:false` 原生参数**（派生输入的 `child_apps_raw` 属此类，会暴露；用户填它、copier 算 `child_apps`），**仅 `derived:true` 纯派生值不暴露** → 跨端共享同名（auth_mode）**去重成单选项**，值广播到两端 copier（merge 已保证属主）。
- **删 `-D` + 精选别名**（⑦ 定案）——schema 数据驱动后无需自由透传；底座加参数 = params.json 自动出现选项（零桥改动保留）。

### 3.3 删逃生舱连带
- `generate` 下不再有 `--frontend/--backend`（子命令即 combo，天然成对/互斥消失）；未知 combo = 无子命令 → 拒绝。

### 3.4 check 子命令迁 Click
- `bridge check --combo/--all/--base-repo/--base-version`，逻辑同 §2.5。

### 3.5 测试连带
- runner/e2e/CLI 单测调用方式全改（命令形态变化）；`--skip-tasks` 保留。

---

## 4. 不在本轮 / 后续待办

- **契约多 edge 目录**（`docs/contracts/`）：需新组合（ui-bff-api）落地后才有意义；
- **新底座接入**（nuxt-fullstack / bff-gateway / cli）：三件套 + combos.yaml units/edges 注册 + 契约模板；
- **`templates/project-README/` 通用化**：目录表 units key 注入；
- **bridge-mcp-server 文档同步 + 实现**：桥成最终态后再据重构结果改 DESIGN.md / 起 FastMCP（不实现代码）。

---

## 5. 测试改动汇总

| 测试 | 改动 |
|---|---|
| tests/test_integrate.py | 删逃生舱用例；适配 Click CLI 形态；merge 测改 merge_answers_by / merge_order |
| tests/test_combos.py | iter_units / edge_pairs / merge_order / param_schema；去兄弟目录断言（改缓存 resolve） |
| tests/test_answers.py | merge 序 python-react 语义 + 多 edge 构造单测 |
| tests/test_params.py / test_coverage.py | 读缓存 params.json；接口随行 |
| tests/test_combos.py（烘焙） | param_schema 分流：mock frozen 读烘焙快照 / 源码读缓存 clone，输出一致 |
| tests/e2e/test_e2e_for_python_react.py | 断言结构不变（frontend/ backend/ docs/CONTRACT.md）；首次需拉底座 |
| tests/utils/runner.py | 适配 Click 命令调用 |

---

## 6. 验收

```bash
uv run pytest                    # 单测 + e2e 全绿（首次拉底座）
uv run bridge check --combo python-react   # 全部对齐
# 手工：uv run bridge generate python-react <tmp> --auth-mode opaque --with-child-app true
#       → frontend/ backend/ docs/CONTRACT.md README.md 结构不变；generate --help 列出 schema 选项
# 打包：uv run python .github/scripts/clone-bases.py --all && uv run pyinstaller integrate.spec
#       → 可执行在无网络/无缓存机器上 --help 仍列出 schema（读烘焙 params.json）
```

---

## 参考
- docs/generation-architecture.md（方案/决策）
- bridge-mcp-server docs/DESIGN.md（能力面工具契约，本轮不改）

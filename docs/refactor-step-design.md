# 生成能力重构 · 步骤化改动设计

> 分支：refactor/nunit-topology ｜ 上游：[docs/generation-architecture.md](generation-architecture.md)（Q1–Q4 已定案）
> 本文件把架构决策翻译成逐文件、逐函数、逐测试的实施步骤，供 Phase A–D 照做。
> **回归护栏**：python-react 组合的 e2e 全程保持绿（见 §8 验收命令）。

---

## 0. 现状关键点（改动前必须核对）

- combos.yaml 每 combo 形如 `{frontend:{source,version}, backend:{source,version}, contract, stack}`。
- `integrate.py`：`build_parser/validate_cli/_combo_config/_ensure_git/resolve_pipeline/collect_user_params/generate/main`；模式 B 逃生舱 = `--frontend/--backend`。
- `bridge/combos.py`：`load_combos/is_url/_load_bases/_frozen_base/resolve_template/resolve_base/ensure_git_repo/declared_params`（后三者按 **source 裸名** 工作，units 复用不改）。
- `bridge/integrate/answers.py`：`read_answers(dest_dir)`、`merge_answers(front,back,user,project_name)`（写死后端优先）。
- `check.py`：全部 `for end in ("frontend","backend")` 假设双端。
- 契约模板：`combos/<combo>/copier.yml`（声明参数并集）+ `CONTRACT.md.jinja`（单文件两端口吻）。
- README 模板：`templates/project-README/`，`README.md.jinja` 硬写 `frontend/ backend/` 目录。
- 测试：`tests/test_integrate.py`（CLI 校验，含逃生舱用例）、`test_combos.py`、`test_answers.py`、`test_coverage.py`、`test_params.py`、`e2e/test_e2e_for_python_react.py`、`utils/runner.py`。

---

## Phase A：数据模型泛化（units/edges）+ integrate N 单元 + 删逃生舱 + check 沿 edges

### A1. combos.yaml 迁移（python-react 示例）

```yaml
combos:
  python-react:
    units:                                  # key = 目录名（Q3）+ project_name 后缀
      frontend: { source: vite-react-spa-template, version: 0034ec9 }
      backend:  { source: python-fastapi-template, version: c73aa7b }
    edges: [[frontend, backend]]            # 有序对 [consumer, provider]：provider 为契约属主
    stack: { ... }                          # 不变
```

- 契约目录 = `combos/<combo>`（去掉 `contract:` 字段，现 python-react 冗余同名；保留向后兼容：若出现 `contract` 字段仍覆盖目录名）。
- `bases:` 段不变。

### A2. bridge/combos.py：新增 units/edges 访问器（不改解析底座逻辑）

```python
def iter_units(combo: dict) -> list[tuple[str, dict]]:
    """(key, unit{source,version})，按声明序。"""
    return list(combo["units"].items())

def iter_unit_sources(combo: dict) -> list[str]:
    return [u["source"] for _, u in iter_units(combo)]

def edge_pairs(combo: dict) -> list[tuple[str, str]]:
    """edges → [(consumer_key, provider_key), ...]，校验 key 存在。"""
    keys = set(combo["units"])
    pairs = []
    for e in combo.get("edges", []):
        c, p = e if isinstance(e, (list, tuple)) else (e["from"], e["to"])
        if c not in keys or p not in keys:
            raise SystemExit(f"❌ edges 引用了不存在的 unit key: {e}")
        pairs.append((c, p))
    return pairs
```

- `declared_params(combo_name)`：契约参数在 combos/\<combo\>/copier.yml 统一声明（含多 edge 并集），**逻辑不变**。
- 兼容旧格式：若 combo 无 `units` 而仍为 `frontend/backend` 平铺，`iter_units` 翻译之（迁移期双读），A 完成后删除兜底。

### A3. integrate.py 重写为 N 单元循环（单模式，无逃生舱）

- **CLI**：删 `--frontend/--backend`。保留 `combo project [-D ...] [精选别名] [--skip-tasks]`。
- `validate_cli` 简化为「必须给 combo」（成对/互斥逻辑整段删除）。
- `resolve_pipeline` → `resolve_combo(name, combos) -> ComboPlan`：

```python
class ComboPlan:
    name: str
    units: list[tuple[str, str, str | None]]   # (key, template_src, version)
    edges: list[tuple[str, str]]
    contract_dir: Path
    stack: dict
```

- `generate(plan, project_dir, project_name, user_params, skip_tasks)`：

```python
for key, src, version in plan.units:
    src = resolve_template(src, version)          # 复用现有
    ensure_git_repo(src)
    data = {"project_name": f"{project_name}-{key}", "project_title": project_name, **user_params}
    run_copier(src, project_dir / key, data, trust=True, skip_tasks=skip_tasks)

# answers 按 key 收集
answers = {key: read_answers(project_dir / key) for key, *_ in plan.units}
merged = merge_answers_by(plan, answers, user_params, project_name)   # A4

run_copier(str(plan.contract_dir), project_dir / "docs", merged, ...)
run_copier(str(BRIDGE / "templates" / "project-README"), project_dir, {**merged, **plan.stack}, ...)
```

- 输出汇报改为遍历 `plan.units`（`project/<key>/`），README/CONTRACT 见 Phase B。

### A4. answers 合并：`merge_answers_by(plan, answers, user_params, project_name)`

- 取代写死 `merge_answers(front, back, ...)`。规则（Q per-edge 属主，Phase C 细化）：
  - 基序 = **provider 覆盖 consumer**（consumer 在前、provider 在后 → dict.update 后者赢）；
  - 链式时最深 provider（api）最末、优先最高：`dominance = [consumer...] + [providers...]` 反拓扑；
  - `user_params` 始终最后（最高优先）；`project_name` 强制为原始名。
- python-react：`[frontend, backend]` 序 → 等价现行为（regression 保持）。
- 单测断言原 `user > backend > frontend` 语义在 python-react 上不变。

### A5. check.py：双端假设 → 沿 units/edges

- `_check_drift`：`for end in ("frontend","backend")` → `for key, unit in iter_units(combo)`，报错前缀 `[name {key}]`。
- `select_targets`（--base-repo）：命中任一 unit source 的组合都入选。
- `_union_params`：遍历全部 units 的 `params.json` 并集（同现状，units 数 ≥2）。
- `_check_subset/_check_coverage`：契约声明集仍读 combos/\<combo\>/copier.yml（A2 不变）→ 逻辑不变。
- 输出文案 `frontend/backend` → unit key 名。

### A6. 删除逃生舱（Q4）连带清理

- `test_integrate.py` 删逃生舱用例：`test_validate_cli_pairing_missing_backend / missing_both / ok_explicit / mutex`；`Args` 删 `frontend/backend` 字段。
- `validate_cli` 保留单测改为「combo 必填」「未知 combo 拒绝」。
- 文档/README 删除模式 B 相关注记（README.md 主文件——桥仓根 README 与 `templates/project-README/README.md.jinja` 是两份，改前者；后者涉及目录引用见 Phase B）。

### A7. Phase A 验收

```bash
uv run pytest tests/unit 2>/dev/null || uv run pytest   # 全绿
uv run pytest tests/e2e/test_e2e_for_python_react.py     # 回归 e2e 绿
uv run check.py --combo python-react                      # 全部对齐
```

---

## Phase B：单模板路径边界 + units-key 布局数据化

> 说明：单模板直生成（`generate_single`）落在 **bridge-mcp-server 能力层**，不在本仓（见 generation-architecture §2 / DESIGN §6）。本仓 Phase B 只做：**布局/引用数据化** + **params.json 边界文档化**。

### B1. project-README 模板：目录引用按 units key 注入

- `templates/project-README/copier.yml` 增补列表参数：
  ```yaml
  units:  # [{key, src_label, app, stack}] —— 由 integrate 生成喂入，渲染目录表
    type: yaml
    when: false
  unit_layout: { type: str, default: "" }   # 生成目录描述文本
  ```
- `README.md.jinja` 目录表改为遍历 units 渲染，去掉硬写 `frontend/`、`backend/` 行；多端时保留 `docs/CONTRACT.md` 索引行。

### B2. integrate.py 喂 README 数据

- generate() 里 `{**merged, **plan.stack, units: <由 units+各端 app 名构成的 list>, ...}`；单单元不在本仓不渲染（能力层直接 copier 底座自带 README）。

### B3. 契约模板对端目录引用数据化（Q3 硬引用清理）

- 扫描 combos/\<combo\>/CONTRACT.md.jinja 中所有字面 `frontend/` / `backend/`（本仓现仅 python-react）：改为经 copier.yml 传入的 unit key 渲染（如 `{{ unit_key_front }}` 或契约模板内 `_computed`），或在契约文案中用「本单元 docs」措辞弱化具体路径。
- 目标：换 units key（如 ui/api）后契约不断引用。

### B4. params.json 边界文档化（优化点 6）

- 在 README 或 docs/base-onboarding.md 补一段：params.json 只服务**多端治理**（底座参数变 → 桥契约是否跟随）；单模板直生成不需 params.json。
- 协议仓 zero 改动，纯文档。

---

## Phase C：契约 per-combo 结构 + 多 edge 文档 + per-edge 合并细化（解锁类型① 含 BFF）

### C1. 契约模板目录支持多 edge 文档（Q2）

- **机制**：integrate 契约渲染目标仍为 `docs/`（copier 把模板目录整树拷去）。python-react（1 edge）维持 `copier.yml + CONTRACT.md.jinja` 现状，输出 `docs/CONTRACT.md`（回归）。
- **多 edge 组合新增**：`combos/<combo>/copier.yml`（参数并集不变）+ `CONTRACT.md.jinja`（边界图 + 各 edge 索引）+ `contracts/<edge>.md.jinja`（每 edge：共享接口 + 两端侧章节），经 copier 拷至 `docs/CONTRACT.md` + `docs/contracts/<edge>.md`。
- copier.yml 参数在**组合根单份**声明（并集），各 `*.jinja` 共享——不按文件重复声明。
- 1-edge 与多 edge 的差异 = 模板作者放了几个 `*.jinja`，integrate.py 无分支。

### C2. 契约叙述端名按 units key（承接 B3）

- 多 edge 模板内用 key 名（ui/bff/api）写「侧」，配合契约数据里注入的 `unit_keys` 渲染；契约属主表述用 provider（Q per-edge）。

### C3. per-edge 合并语义落定（A4 细化）

- 明确 provider 覆盖方向为「契约属主」；中间单元（BFF）对 C1 是 provider、对 C2 是 consumer：合并时其 answers 中「仅自身声明、不与他端同名冲突」的参数照常进并集；同名冲突由最深 provider 赢。
- 派生参数（when:false）仍由 copier 计算，禁止传入（合并层不产生派生值）。

### C4. 接线下沉底座 docs（Q1 落地）

- 新前端底座（如 Nuxt fullstack）把「CORS/SSR/BFF 对接」写进**该底座 docs** 固定章节；契约模板只按单位引用，不复制接线实现、不做 kind 分支。edge `transport: cors|direct` 声明进 combos.yaml（供 README/QA，不进模板分支）。

---

## Phase D：能力层 + 可执行 + 新底座（跨仓/后续）

- **bridge-mcp-server**：按 DESIGN §6 起 FastMCP 骨架；`generate_single(git_url)` clone→指 template/→copier；`get_template_params(git_url)` clone 内省；`generate_multi` shell-out 本仓 integrate（单模式，已无逃生舱）；`list_combos` 只列多端组合。
- **可执行分发**：`dist/integrate` 保持（多端）；薄核心如需分发按同模式打包（PyInstaller + frozen 克隆缓存）。
- **新底座接入**（nuxt-fullstack / bff-gateway / cli）：三件套 params.json 协议；契约 per-combo；combos.yaml 注册 units/edges。

---

## 测试迁移矩阵（汇总）

| 测试 | 改动 |
|---|---|
| tests/test_integrate.py | 删逃生舱用例；`Args` 去 frontend/backend；validate 改「combo 必填/未知拒绝」；合并测试改 `merge_answers_by` |
| tests/test_combos.py | 加 iter_units / iter_unit_sources / edge_pairs 单测（含 edges 引用不存在 key 抛错） |
| tests/test_answers.py | 兼容层：`merge_answers_by` python-react 上保持 user>backend>frontend 语义断言 |
| tests/test_params.py / test_coverage.py | 接口未动则不变；若 `_union_params` 签名变则跟进 |
| tests/e2e/test_e2e_for_python_react.py | 断言不变（frontend/ backend/ 目录仍在 → 回归）；跑通即护栏 |
| tests/utils/runner.py | `run_integrate` 已按 combo 参数化，基本不变 |

---

## 风险 / 待确认

1. **契约源目录 1-edge vs 多 edge 并存**（C1）——python-react 不挪，避免回归；差异在集成测试覆盖而非代码分支。
2. **合并属主反拓扑序**（A4/C3）——python-react 无感知，三单元链（ui-bff-api）首个落地时以 e2e 校验，必要时引入显式 `edge.owner` 覆盖默认「provider 赢」。
3. **README 目录表 units 列表数据**（B1/B2）——需定 unit 展示字段（src_label/app/stack 从哪取），现 stack 元数据在 combos.yaml 每端平铺，迁移后放 combo.stack + 每 unit 名。
4. **能力层不在本仓**——`generate_single` 等是 bridge-mcp-server 范围，本仓 Phase B/D 只保证「单模式 CLI + 数据驱动布局」，跨仓联调在 Phase D。

---

## 参考
- docs/generation-architecture.md（方案/决策）
- bridge-mcp-server docs/DESIGN.md（能力面工具契约）

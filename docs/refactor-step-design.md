# 生成能力重构 · 步骤化改动设计

> 分支：refactor/nunit-topology ｜ 上游：[docs/generation-architecture.md](generation-architecture.md)（Q1–Q4 已定案）
> **本轮范围（已定案）**：代码支持多 units 模式（N≥2、含多 edge）+ 更新桥仓根 README.md + docs/base-onboarding.md。
> 新底座接入、能力层（bridge-mcp-server）实现/文档同步、`templates/project-README/` 通用化均**不在本轮**（见「后续待办」）。
> **回归护栏**：python-react 组合的 e2e 全程保持绿（见 §验收）。

---

## 0. 本轮边界（精确）

**做**：
1. combos.yaml / integrate.py / check.py / `.github/scripts/clone-bases.py` 从「双端平铺」泛化为「多 units + edges（N≥2）」，删逃生舱——以现有 python-react（units=2、**单 edge**）为唯一回归样本；数据结构/访问器按**多 edge 可表达**实现（ui-bff-api 形态将来可直接落地）。
2. 文档随新形态更新：桥仓根 `README.md`（删模式 B、组合映射改 units 表述）+ `docs/base-onboarding.md`（接入规则同步 units）。

**不做**：
- 不接入任何新底座（nuxt-fullstack / bff-gateway / cli）；
- 不改契约多 edge 目录结构（`docs/contracts/`）——python-react 单 edge 维持 `docs/CONTRACT.md` 现状；
- 不改 bridge-mcp-server 任何文件；
- 不改 `templates/project-README/`（python-react 输出 frontend/backend 恰好不变，通用化留待多 units 组合落地时）；
- 精简 CLI 别名（`-D` 透传 / 精选别名去留）——**待定，见 §3**，本轮默认保留不动。

---

## 1. 本轮改动清单（逐文件）

### 1.1 combos.yaml：python-react 迁移 units/edges

```yaml
combos:
  python-react:
    units:                                  # 每项 {source, version}（同现 frontend/backend 内结构）
      frontend: { source: vite-react-spa-template, version: 0034ec9 }
      backend:  { source: python-fastapi-template, version: c73aa7b }
    edges: [[frontend, backend]]            # 有序对 [consumer, provider]；provider 契约属主
    stack: { ... }                          # 不变
```

- **去掉 `contract:` 字段，契约目录固定 = combos/\<combo\>**（python-react 原冗余同名；④ 定案）。
- `edges` **必填显式**（不做「缺省 = 相邻全连」隐式推断）；值为有序对列表，**支持多 edge**（如未来 `[[ui,bff],[bff,api]]`；③ 定案）。
- `bases:` 段不变。
- **不做旧格式兜底**（仓库仅 python-react，硬切；⑥ 定案）。

### 1.2 bridge/combos.py：新增 units/edges 访问器

```python
def iter_units(combo):        # -> [(key, {source, version})]，按声明序
def iter_unit_sources(combo): # -> [source, ...]
def edge_pairs(combo):        # -> [(consumer_key, provider_key), ...]
    # edges 必填、有序对、支持多 edge；校验每个 key ∈ units，否则 SystemExit
```

- 解析底座逻辑（resolve_template / resolve_base / ensure_git_repo / _frozen_base）按 source 工作，**复用不改**。
- `declared_params(combo)` 读 combos/\<combo\>/copier.yml，**逻辑不变**。
- 不做旧格式兜底（⑥ 定案）：load_combos 后直接按 units/edges 消费，不再读 `combo["frontend"]` 平铺。

### 1.3 integrate.py：N 单元循环 + 删逃生舱

- **CLI**：删 `--frontend/--backend`；保留 `combo project [-D …] [精选别名] [--skip-tasks]`。
- `validate_cli`：简化为「combo 必填 + 在注册表内」（互斥/成对逻辑删除）。
- 新增 `ComboPlan`：`name / units[(key, src, version)] / edges / contract_dir / stack`；`resolve_combo(name, combos) -> ComboPlan`（替代 resolve_pipeline）。
- `generate(plan, project_dir, project_name, user_params, skip_tasks)`：遍历 units → `run_copier(src, project_dir/key, {"project_name": f"{project_name}-{key}", …})` → 按 key 收集 answers → 合并 → 渲染契约至 docs/ → 渲染 README。
- 汇报：遍历 plan.units（`project/<key>/`）。
- `_ensure_git` 作用于 `iter_unit_sources(combo)`。

### 1.4 merge_answers → per-edge 属主合并

- `merge_answers_by(plan, answers_by_key, user_params, project_name)`：
  - **单 edge**（python-react）：序 = consumer 先、provider 后（dict.update 后者赢）→ `[frontend, backend]` 序 ≡ 现 `user > backend > frontend`；
  - **多 edge**（数据结构支持，ui-bff-api 形态）：合并序沿 edges 推导——consumer→provider、provider 为属主、最深 provider 最末赢；本轮无真实验证样本，单测用构造 combo 覆盖；
  - user_params 最末（最高优先）；project_name 强制原始名；
  - 实现：把 edges 展平成合并序列表传入（合并函数本身不关心 units 数），`python-react` 传 `[frontend, backend]`。
- 保留 `read_answers` 不变。

### 1.5 check.py：双端假设 → 沿 units

- `_check_drift` / `_union_params`：`for end in ("frontend","backend")` → `for key, unit in iter_units(combo)`，前缀 `[name {key}]`。
- `select_targets`（--base-repo）：命中任一 unit source 的组合入选。
- `_check_subset/_check_coverage` 读 declared_params，不变。

### 1.6 `.github/scripts/clone-bases.py`：双端遍历 → 沿 units

- [第 29/36 行](.github/scripts/clone-bases.py#L29)：`for end in ("frontend","backend")` → `for _, unit in iter_units(c)` 取 `unit["source"]`；
- [第 34 行](.github/scripts/clone-bases.py#L34)：`c["frontend"]["source"] == args.for_base or c["backend"]["source"]` → 改用 `args.for_base in iter_unit_sources(c)`；
- `bases:` 注册表消费逻辑不变。

### 1.7 桥仓根 README.md：随新形态更新

- 结构表：integrate/combos.yaml/check 描述对齐「多 units + edges」。
- 快速开始：删**模式 B 示例与全部逃生舱说明**；保留单命令（原模式 A 即为唯一方式）。
- 组合映射示例：`units:` + `edges:` 形态（⑤：**units 表述**）。
- 契约约定段：合并优先级改 per-edge 措辞（python-react 仍后端主）；去「模式 B git 地址不提供契约」等。
- 「加新组合 = 加一行 + 新建契约目录」表述顺带对齐 units/edges 措辞。

### 1.8 docs/base-onboarding.md：接入规则同步 units（⑤）

- §2 桥侧登记 2.1 的 combos.yaml 示例：`frontend/backend` 平铺 → `units:` + `edges:`（**同步修改，非本轮只改 README**）；
- 说明「多单元组合用 edges 声明契约边；单单元形态不在桥（走能力层 generate_single，属后续）」；
- 其余（三件套 / GitHub 配置步骤）不变。

### 1.9 测试

| 测试 | 改动 |
|---|---|
| tests/test_integrate.py | 删逃生舱用例（mutex / pairing_* / ok_explicit）；Args 去 frontend/backend；validate 单测改「combo 必填/未知拒绝」；合并测改 merge_answers_by |
| tests/test_combos.py | 加 iter_units / iter_unit_sources / edge_pairs（含 edges 引用不存在 key 抛错；构造多 edge combo 断言返回多对） |
| tests/test_answers.py | merge_answers_by 在 python-react 保持 user>backend>frontend 断言；加构造多 edge 链的合并序单测 |
| tests/test_params.py / test_coverage.py | 接口未动则不变 |
| tests/e2e/test_e2e_for_python_react.py | 断言不变（frontend/ backend/ 目录仍在 → 回归护栏） |
| tests/utils/runner.py | 基本不变 |

---

## 2. 验收

```bash
uv run pytest                    # 单测 + e2e 全绿
uv run check.py --combo python-react   # 全部对齐
# 手工：python integrate.py python-react <tmp> --auth-mode opaque --with-child-app true
#       → 确认 frontend/ backend/ docs/CONTRACT.md README.md 结构不变
```

---

## 3. 本轮待定项

- **CLI 别名去留**（⑦）：`-D key=value` 通用透传与精选别名（`--auth-mode` 等）是否保留/精简——**稍后讨论**，本轮默认保留不动（改动清单不含别名精简）。

---

## 4. 后续待办（不在本轮）

- **契约多 edge 目录**（Phase C，generation-architecture §4）：`docs/CONTRACT.md` 索引 + `docs/contracts/<edge>.md`；契约模板 per-combo 内多 `*.jinja`。需新组合（如 ui-bff-api）落地后才有意义。
- **新底座接入**（nuxt-fullstack / bff-gateway / cli）：三件套 params.json 协议 + combos.yaml 注册 units/edges + 契约模板。本轮排除。
- **`templates/project-README/` 通用化**：目录表改 units key 注入渲染（本轮 python-react 输出恰不变，暂缓）。
- **bridge-mcp-server 文档同步**：重构完成、桥形态成最终态后再据重构结果改 DESIGN.md（§5/§6.2 去「模式 A」、§6.5 list_combos 去 contract 字段、§8 units 形态、§12 参考）。不实现代码。
- **bridge-mcp-server 能力层实现**：FastMCP 骨架等，另行立项。

---

## 参考
- docs/generation-architecture.md（方案/决策）
- bridge-mcp-server docs/DESIGN.md（能力面工具契约，本轮不改）

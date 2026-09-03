"""组合解析：combos.yaml 加载、units/edges 访问、底座统一 clone（砍本地模式）。

设计（refactor-step-design §1/§2）：
- 底座一律 clone 到缓存并 checkout combos.yaml version——无源码兄弟目录分支；
- params.json 从缓存 clone 读（钉 version 后 checkout，天然对齐）；
- source 为注册裸名（bases 注册表）——与 generation-architecture Q4 一致，
  多端只认注册组合，不支持显式 URL/本地路径（单模板形态走能力层 generate_single）。
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml

from . import BRIDGE

_FROZEN = getattr(sys, "frozen", False)

COMBO_FILE = BRIDGE / "combos.yaml"
# 底座统一克隆缓存（combos.yaml version checkout）——clone-bases.py / spec 共享
BASE_CACHE = Path.home() / ".cache" / "fullstack-bridge" / "bases"


def load_combos() -> dict:
    return yaml.safe_load(COMBO_FILE.read_text(encoding="utf-8"))["combos"]


def validate_combo(combo_name: str, combo: dict) -> None:
    """形态约束：units≥2、edges 必填、端点合法、source 注册、链形（R5）。桥只管 N≥2。"""
    units = combo.get("units", {})
    if not isinstance(units, dict) or len(units) < 2:
        raise SystemExit(f"❌ 组合 {combo_name} units < 2——桥只管理多单元组合（N≥2）")
    if not combo.get("edges"):
        raise SystemExit(f"❌ 组合 {combo_name} 缺 edges（必填显式）")
    edge_pairs(combo)  # 端点合法性校验（缺 key 抛错）
    # source 注册性：units.source 须在 bases 注册表（Q4 只认注册裸名）
    bases = _load_bases()
    for key, unit in combo["units"].items():
        src = unit.get("source")
        if src not in bases:
            raise SystemExit(
                f"❌ 组合 {combo_name} unit「{key}」source「{src}」未在 bases 注册表"
            )
    # 链形：edges 数应 = units-1（系列目前只支持链式契约；未来若支持星型/环型再放宽）
    if len(combo["edges"]) != len(units) - 1:
        raise SystemExit(
            f"❌ 组合 {combo_name} edges 数 {len(combo['edges'])} ≠ units-1"
            f"（{len(units) - 1}）——契约仅支持链形"
        )


def validate_all_combos() -> None:
    for name, combo in load_combos().items():
        validate_combo(name, combo)


def _load_bases() -> dict:
    """combos.yaml 的 bases 注册表（底座名 → git 地址）。"""
    return yaml.safe_load(COMBO_FILE.read_text(encoding="utf-8")).get("bases", {})


# ── units/edges 访问器（§2.2）──────────────────────────────────────


def iter_units(combo: dict) -> list[tuple[str, dict]]:
    """(key, {source, version})，按声明序。"""
    return list(combo["units"].items())


def iter_unit_sources(combo: dict) -> list[str]:
    return [u["source"] for _, u in iter_units(combo)]


def edge_pairs(combo: dict) -> list[tuple[str, str]]:
    """edges → [(consumer_key, provider_key), ...]；校验 key ∈ units。"""
    keys = set(combo["units"])
    pairs = []
    for e in combo.get("edges", []):
        c, p = e if isinstance(e, (list, tuple)) else (e["from"], e["to"])
        if c not in keys or p not in keys:
            raise SystemExit(f"❌ edges 引用了不存在的 unit key: {e}")
        pairs.append((c, p))
    return pairs


def merge_order(combo: dict) -> list[str]:
    """edges 展平成合并序：consumer→provider 序，中间单元去重（首现保留）。

    供 merge：dict.update 按此序，后者（provider/更深）赢；python-react
    [frontend, backend] 序 ≡ 现 `user > backend > frontend`。
    """
    order: list[str] = []
    for c, p in edge_pairs(combo):
        if c not in order:
            order.append(c)
        if p not in order:
            order.append(p)
    return order


# ── 底座统一 clone（§1.1）─────────────────────────────────────────


def _ensure_base(source: str, version: str | None = None) -> Path:
    """clone 裸名底座到缓存 → checkout version → 返回仓库根。

    git 地址从 combos.yaml bases 注册表取；依赖 git + 网络（首次）。
    source 须为裸名（URL/显式路径由 resolve_* 在上层原样处理）。
    """
    url = _load_bases().get(source)
    if not url:
        raise SystemExit(f"❌ combos.yaml bases 未配置「{source}」的 git 地址")
    dest = BASE_CACHE / source
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"↻ clone {url} → {dest}")
        subprocess.run(["git", "clone", url, str(dest)], check=True)
    if version:
        cur = subprocess.run(
            ["git", "-C", str(dest), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        if cur != version:
            _checkout_or_fetch(dest, version)
    return dest


def _checkout_or_fetch(dest: Path, version: str) -> None:
    """checkout 到 version；本地缺该 sha（缓存旧）→ fetch origin 后重试（S4）。"""
    r = subprocess.run(
        ["git", "-C", str(dest), "checkout", version],
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        return
    print(f"↻ 本地缺 {version[:12]}——fetch origin 后重试")
    subprocess.run(["git", "-C", str(dest), "fetch", "origin"], check=True)
    r = subprocess.run(
        ["git", "-C", str(dest), "checkout", version],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise SystemExit(
            f"❌ 底座 {dest.name} checkout {version} 失败（fetch 后仍不可得）: "
            f"{r.stderr.strip()}"
        )


def fetch_base(source: str) -> None:
    """刷新底座缓存 clone 的远端 ref（origin/HEAD）（R2）。

    check 用——让漂移「当前」参照反映上游最新；离线失败仅提示，不中断（沿用现有 ref）。
    """
    dest = BASE_CACHE / source
    if not (dest / ".git").exists():
        return  # 未 clone：drift 的 resolve_base 自会处理
    r = subprocess.run(
        ["git", "-C", str(dest), "fetch", "origin"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(
            f"⚠️ 底座 {source} fetch origin 失败（{r.stderr.strip()[:80]}）——沿用本地 ref"
        )


def resolve_template(source: str, version: str | None = None) -> str:
    """底座（注册裸名）→ 模板目录 template/：clone 缓存 + checkout version。

    source 须为 bases 注册裸名（S1：与 Q4 一致，多端只认注册组合）。
    """
    base = _ensure_base(source, version)
    return str(base / "template")


def resolve_base(source: str, version: str | None = None) -> Path:
    """底座（注册裸名）git 仓库根：clone 缓存 + checkout version。

    check 读 params.json 用（git show / 工作树皆可，clone 得全量历史）。
    """
    return _ensure_base(source, version)


def declared_params(combo_name: str) -> set[str] | None:
    """组合契约模板（combos/<combo>/copier.yml）声明的参数集（决策③ 检查基线）。"""
    cp = BRIDGE / "combos" / combo_name / "copier.yml"
    if not cp.exists():
        print(f"⚠️ 缺组合契约模板 combos/{combo_name}/copier.yml")
        return None
    data = yaml.safe_load(cp.read_text(encoding="utf-8"))
    return {k for k in data if not k.startswith("_")}


def _frozen_params_path(source: str) -> Path | None:
    """frozen（可执行）模式的烘焙 params.json：_MEIPASS/bases_params/<source>.json。"""
    baked = BRIDGE / "bases_params" / f"{source}.json"
    return baked if baked.exists() else None


def param_schema(combo_name: str, combo: dict) -> dict[str, dict]:
    """组合参数 schema：各 unit params.json 并集（§2.3）。

    暴露全部 derived:false 原生参数（含派生输入如 child_apps_raw）；仅 derived:true
    纯派生值不暴露。跨 unit 同名参数（共享）去重，spec 取 **provider 端**（S2）：
    provider 为契约属主，default/choices 以其为准；consumer 端同名不覆盖。
    对共享参数的 default / enabled choices 跨端不一致 → 告警（提示底座默认漂移）。

    读参分流（§1.4）：frozen 读烘焙 _MEIPASS/bases_params；源码读缓存 clone（钉 version）。
    """
    # 先按 unit key 收齐各自 params（仅原生参数）
    per_unit: dict[str, dict[str, dict]] = {}
    for key, unit in iter_units(combo):
        baked = _frozen_params_path(unit["source"]) if _FROZEN else None
        p = (
            baked
            if baked is not None
            else _ensure_base(unit["source"], unit.get("version")) / "params.json"
        )
        if not p.exists():
            print(f"⚠️ 缺底座 {unit['source']} params.json（{p}）——跳过其参数")
            continue
        params = json.loads(p.read_text(encoding="utf-8")).get("params", {})
        per_unit[key] = {n: s for n, s in params.items() if not s.get("derived")}

    providers = {p for _, p in edge_pairs(combo)}  # 所有 edge 的 provider key（S2）

    def _default_and_choices(spec: dict):
        return (
            spec.get("default"),
            [c["value"] for c in spec.get("choices", []) if not c.get("disabled")],
        )

    # 身份参数：各端可有独立默认（project_name/project_title），非契约决策——不做共享一致校验
    _identity_params = {"project_name", "project_title"}

    schema: dict[str, dict] = {}
    for key, params in per_unit.items():
        for name, spec in params.items():
            if name in schema:
                if name in _identity_params:
                    continue  # 各端身份自持，不 provider 覆盖也不告警
                # 共享契约参数：校验跨端 default/enabled choices 一致；不一致告警（不静默取一）
                old_spec = schema[name]
                if _default_and_choices(old_spec) != _default_and_choices(spec):
                    old_unit = old_spec.get("unit_key")
                    print(
                        f"⚠️ 共享参数 {name} 在 {old_unit} 与 {key} 的默认值/启用取值"
                        f"不一致（{_default_and_choices(old_spec)} vs "
                        f"{_default_and_choices(spec)}）——取 provider 端"
                    )
                if key in providers and old_spec.get("unit_key") not in providers:
                    schema[name] = {**spec, "unit_key": key}  # provider 端覆盖 consumer
                continue
            schema[name] = {**spec, "unit_key": key}
    return schema

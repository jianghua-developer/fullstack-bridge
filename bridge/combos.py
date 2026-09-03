"""组合解析：combos.yaml 加载、units/edges 访问、底座统一 clone（砍本地模式）。

设计（refactor-step-design §1/§2）：
- 底座一律 clone 到缓存并 checkout combos.yaml version——无源码兄弟目录分支；
- params.json 从缓存 clone 读（钉 version 后 checkout，天然对齐）；
- 显式本地路径 / git URL 原样（dev/逃生保留），但裸名 = 一律 clone。
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
_BASE_CACHE = BASE_CACHE  # 内部别名（保留旧引用兼容）


def load_combos() -> dict:
    return yaml.safe_load(COMBO_FILE.read_text(encoding="utf-8"))["combos"]


def is_url(source: str) -> bool:
    return "://" in source or source.startswith("git@")


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
    dest = _BASE_CACHE / source
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
            subprocess.run(["git", "-C", str(dest), "checkout", version], check=True)
    return dest


def resolve_template(source: str, version: str | None = None) -> str:
    """底座 → 模板目录（template/ 子目录）；显式路径/git URL 原样。

    裸名一律 clone 缓存 + checkout version（无源码兄弟目录分支）。
    """
    if is_url(source) or source.startswith(("/", "./", "../")):
        return source
    base = _ensure_base(source, version)
    return str(base / "template")


def resolve_base(source: str, version: str | None = None) -> Path:
    """底座 git 仓库根：裸名 → 缓存 clone（checkout version）；显式路径原样。

    check 读 params.json 用（git show / 工作树皆可，clone 得全量历史）。
    """
    if is_url(source):
        raise ValueError(f"git 地址需先克隆才能解析本地 base: {source}")
    if source.startswith(("/", "./", "../")):
        return Path(source)
    return _ensure_base(source, version)


def ensure_git_repo(source: str) -> None:
    """底座必须可解析为 git 仓。裸名经 clone 天然是；显式本地路径须为 git 检出。"""
    if is_url(source):
        return  # git URL，clone 时得 git
    if source.startswith(("/", "./", "../")):
        target = Path(source)
        r = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise SystemExit(
                f"❌ 底座 {target} 不是 git 仓库（显式本地路径须为 git 检出）"
            )
        return
    _ensure_base(source)  # 裸名：clone 即可，天然 git


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

    暴露全部 derived:false 原生参数（含派生输入如 child_apps_raw）；
    仅 derived:true 纯派生值不暴露。跨 unit 同名合并（保留首现 spec）。
    返回：{param_name: {type, choices, default, derived, unit_key}}（unit_key=None=共享）

    读参分流（§1.4）：frozen 读烘焙 _MEIPASS/bases_params；源码读缓存 clone（钉 version）。
    """
    schema: dict[str, dict] = {}
    for key, unit in iter_units(combo):
        baked = _frozen_params_path(unit["source"]) if _FROZEN else None
        if baked is not None:
            p = baked
        else:
            base_dir = _ensure_base(unit["source"], unit.get("version"))
            p = base_dir / "params.json"
        if not p.exists():
            print(f"⚠️ 缺底座 {unit['source']} params.json（{p}）——跳过其参数")
            continue
        params = json.loads(p.read_text(encoding="utf-8")).get("params", {})
        for name, spec in params.items():
            if spec.get("derived"):
                continue  # 纯派生值不暴露（derived:true，如 child_apps）
            if name in schema:
                continue  # 跨 unit 同名 → 共享，保留首现（合并/广播语义）
            schema[name] = {**spec, "unit_key": key}
    return schema

"""组合解析：combos.yaml 加载、模板/底座解析、git 校验。"""

import subprocess
from pathlib import Path

import yaml

from . import BRIDGE

COMBO_FILE = BRIDGE / "combos.yaml"


def load_combos() -> dict:
    return yaml.safe_load(COMBO_FILE.read_text(encoding="utf-8"))["combos"]


def is_url(source: str) -> bool:
    return "://" in source or source.startswith("git@")


def resolve_template(source: str) -> str:
    """系列底座名 → ../<name>/template；显式本地路径 / git 地址原样。"""
    if is_url(source) or source.startswith(("/", "./", "../")):
        return source
    return str(BRIDGE.parent / source / "template")


def resolve_base(source: str) -> Path:
    """底座 git 仓库根：系列底座名 → ../<name>；显式本地路径原样；git 地址需先克隆。"""
    if is_url(source):
        raise ValueError(f"git 地址需先克隆才能解析本地 base: {source}")
    if source.startswith(("/", "./", "../")):
        return Path(source)
    return BRIDGE.parent / source


def ensure_git_repo(source: str) -> None:
    """底座必须是 git 仓（检查链依赖 params.json version 基线）；非 git 直接拒绝。"""
    if is_url(source):
        return  # git URL，copier / check 克隆
    target = resolve_base(source)
    r = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise SystemExit(
            f"❌ 底座 {target} 不是 git 仓库——检查链依赖 git 基线（params.json version），"
            f"本地底座必须是 git 检出"
        )


def declared_params(combo_name: str) -> set[str] | None:
    """组合契约模板（combos/<combo>/copier.yml）声明的参数集（决策③ 检查基线）。"""
    cp = BRIDGE / "combos" / combo_name / "copier.yml"
    if not cp.exists():
        print(f"⚠️ 缺组合契约模板 combos/{combo_name}/copier.yml")
        return None
    data = yaml.safe_load(cp.read_text(encoding="utf-8"))
    return {k for k in data if not k.startswith("_")}

"""组合解析：combos.yaml 加载、模板/底座解析、git 校验。"""

import subprocess
import sys
from pathlib import Path

import yaml

from . import BRIDGE

COMBO_FILE = BRIDGE / "combos.yaml"
ORG = "jianghua-developer"
_FROZEN = getattr(sys, "frozen", False)
# 可执行文件（frozen）模式下，裸名底座的克隆缓存（按 combos.yaml version checkout）
_BASE_CACHE = Path.home() / ".cache" / "fullstack-bridge" / "bases"


def load_combos() -> dict:
    return yaml.safe_load(COMBO_FILE.read_text(encoding="utf-8"))["combos"]


def is_url(source: str) -> bool:
    return "://" in source or source.startswith("git@")


def _frozen_base(source: str, version: str | None = None) -> str:
    """可执行文件（frozen）模式：克隆裸名底座到缓存，checkout 对齐版本，返回 template/。

    copier 不能直接消费底座 git URL（copier.yml 在仓库 template/ 子目录）——
    需自行克隆后指向 template/。依赖：git 在 PATH + 网络。
    """
    dest = _BASE_CACHE / source
    if not (dest / "template" / "copier.yml").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", f"https://github.com/{ORG}/{source}.git", str(dest)],
                       check=True)
    if version:
        cur = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        if cur != version:
            subprocess.run(["git", "-C", str(dest), "checkout", version], check=True)
    return str(dest / "template")


def resolve_template(source: str, version: str | None = None) -> str:
    """系列底座名 → 模板目录；显式本地路径 / git 地址原样。

    - 源码模式：兄弟目录 ../<name>/template（version 忽略）
    - frozen（可执行文件）：克隆底座到缓存并 checkout version（combos.yaml 对齐版本）
    """
    if is_url(source) or source.startswith(("/", "./", "../")):
        return source
    if _FROZEN:
        return _frozen_base(source, version)
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
    if _FROZEN and not source.startswith(("/", "./", "../")):
        return  # 可执行文件：裸名底座在 resolve_template 时克隆（走 git）
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

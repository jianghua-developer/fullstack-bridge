#!/usr/bin/env python3
"""clone-bases.py — CI 用：把 combos.yaml 引用的底座克隆到桥的兄弟路径（../<source>）。

本地已有兄弟目录则跳过。drift 检查需能 `git show <sha>:params.json`，故全量拉取历史。
用法：
  clone-bases.py --all                # 克隆全部组合的底座
  clone-bases.py --for-base <名>      # 只克隆用该底座的组合涉及的底座
"""

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

BRIDGE = Path(__file__).resolve().parent.parent.parent  # .github/scripts/ → 桥根
ORG = "jianghua-developer"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--for-base", help="只克隆涉及该底座的组合")
    args = ap.parse_args()

    combos = yaml.safe_load((BRIDGE / "combos.yaml").read_text(encoding="utf-8"))["combos"]
    sources = {c[end]["source"] for c in combos.values() for end in ("frontend", "backend")}
    if args.for_base:
        # 受影响组合（用了该底座的）涉及的**全部**底座——check 的子集对齐要读两端 params
        affected = {
            name for name, c in combos.items()
            if c["frontend"]["source"] == args.for_base or c["backend"]["source"] == args.for_base
        }
        sources = {c[end]["source"] for name in affected for c in (combos[name],) for end in ("frontend", "backend")}
    if not args.all and not args.for_base:
        ap.error("--all 或 --for-base 必给一个")

    for src in sorted(sources):
        dest = BRIDGE.parent / src
        if dest.is_dir():
            print(f"✓ 底座已存在: {src}")
            continue
        url = f"https://github.com/{ORG}/{src}.git"
        print(f"↻ 克隆 {url} → {dest}")
        subprocess.run(["git", "clone", "--filter=blob:none", url, str(dest)], check=True)
        subprocess.run(
            ["git", "-C", str(dest), "fetch", "--unshallow", "origin"],
            check=True, capture_output=True,
        )
        print(f"✓ 已克隆: {src}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

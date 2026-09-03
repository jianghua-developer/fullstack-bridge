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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--for-base", help="只克隆涉及该底座的组合")
    args = ap.parse_args()

    data = yaml.safe_load((BRIDGE / "combos.yaml").read_text(encoding="utf-8"))
    combos = data["combos"]
    bases = data.get("bases", {})  # 底座 git 地址注册表
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
        url = bases.get(src)
        if not url:
            raise SystemExit(f"❌ combos.yaml bases 未配置「{src}」的 git 地址")
        print(f"↻ 克隆 {url} → {dest}")
        # 普通全量克隆（底座仓小）：`--filter=blob:none` 是部分克隆非浅克隆，
        # 对之 `fetch --unshallow` 会报 128；且全量克隆让 check 的 `git show` 不依赖懒加载
        subprocess.run(["git", "clone", url, str(dest)], check=True)
        print(f"✓ 已克隆: {src}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

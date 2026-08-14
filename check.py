#!/usr/bin/env python3
"""check.py — fullstack-bridge 检查链入口（薄编排；逻辑在 bridge/ 包）。

用法：
  check.py --combo python-react                    # 单组合检查（手动 / 桥 CI gate）
  check.py --all                                   # 全部组合
  check.py --base-repo <名> --base-version <sha>   # 漂移检查（check-drift workflow 用）
"""

import argparse
import sys

from bridge.check.coverage import coverage_report
from bridge.check.params import diff_params, read_params
from bridge.combos import declared_params, load_combos, resolve_base


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="fullstack-bridge 检查链")
    p.add_argument("--combo", help="检查指定组合")
    p.add_argument("--all", action="store_true", help="检查全部组合")
    p.add_argument("--base-repo", help="漂移检查：底座名（check-drift 信号）")
    p.add_argument("--base-version", help="漂移检查：底座信号版本（commit/tag）")
    return p


def select_targets(p: argparse.ArgumentParser, args, combos: dict) -> dict:
    """模式选择（--combo / --all / --base-repo）→ 目标组合集。"""
    if args.base_repo:
        if not args.base_version:
            p.error("--base-version 必填（与 --base-repo 配对）")
        targets = {n: c for n, c in combos.items()
                   if c["frontend"]["source"] == args.base_repo or c["backend"]["source"] == args.base_repo}
        if not targets:
            print(f"⚠️ 无组合使用底座 {args.base_repo}")
        return targets
    if args.combo:
        if args.combo not in combos:
            p.error(f"未知组合 {args.combo}（可用: {', '.join(combos)}）")
        return {args.combo: combos[args.combo]}
    if args.all:
        return combos
    p.error("请给 --combo 或 --all（或 --base-repo --base-version）")


def check_combo(name: str, combo: dict, base_repo: str | None, base_version: str | None) -> bool:
    """检查单个组合：检查 1（漂移 + 子集）+ 检查 2（覆盖）。返回是否发现未对齐。"""
    drift = False

    # 检查 1a：pinned 基线 vs 当前/信号版本 漂移
    for end in ("frontend", "backend"):
        src, pinned = combo[end]["source"], combo[end]["version"]
        base_dir = resolve_base(src)
        old, err = read_params(base_dir, pinned)
        if err:
            print(f"✗ [{name} {end}] {err}"); drift = True; continue
        cur_ref = base_version if (base_repo and src == base_repo) else None
        new, err = read_params(base_dir, cur_ref)
        if err:
            print(f"✗ [{name} {end}] {err}"); drift = True; continue
        diffs = diff_params(old, new)
        who = f"信号版本 {cur_ref}" if cur_ref else "当前工作树"
        if diffs:
            print(f"⚠️ [{name} {end}] 底座 {src} 漂移（基线 {pinned} vs {who}）:")
            for d in diffs:
                print(f"    - {d}")
            drift = True
        else:
            print(f"✓ [{name} {end}] {src} 对齐基线 {pinned}")

    # 底座当前参数并集（dict：name → spec）
    union_params = {}
    for end in ("frontend", "backend"):
        cur, _ = read_params(resolve_base(combo[end]["source"]), None)
        if cur:
            union_params.update(cur.get("params", {}))

    # 检查 1b：契约声明参数 ⊆ 底座参数并集
    declared = declared_params(name)
    if declared is not None:
        missing = declared - set(union_params)
        if missing:
            print(f"⚠️ [{name}] 契约声明参数不在底座参数并集（可能版本未对齐）: {sorted(missing)}")
            drift = True
        else:
            print(f"✓ [{name}] 契约声明参数 ⊆ 底座参数并集")

    # 检查 2：底座 enabled choices vs 契约显式覆盖（启发式，限契约声明集）
    hard, advisory = coverage_report(name, union_params, declared)
    for msg in hard:
        print(f"⚠️ [{name}] 检查2 未覆盖: {msg}")
        drift = True
    for msg in advisory:
        print(f"ℹ️ [{name}] 检查2 提示: {msg}")

    return drift


def main() -> int:
    p = build_parser()
    args = p.parse_args()
    combos = load_combos()
    targets = select_targets(p, args, combos)
    if not targets:
        return 0  # 已打印提示

    drift = False
    for name, combo in targets.items():
        if check_combo(name, combo, args.base_repo, args.base_version):
            drift = True

    print("\n" + ("❌ 存在漂移/未对齐" if drift else "✅ 全部对齐"))
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())

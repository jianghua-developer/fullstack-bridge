#!/usr/bin/env python3
"""clone-bases.py — 统一底座获取：把 combos.yaml units 引用的底座克隆到缓存目录。

设计：底座一律 clone/baked，目标 = ~/.cache/fullstack-bridge/bases
（与 bridge.combos.BASE_CACHE 一致），不再克隆到桥的兄弟路径。drift 检查需 `git show <sha>:params.json`，
故全量拉取历史。可加 --collect-params <dir>：把各底座钉 version 的 params.json 拷出（spec 烘焙用）。

用法：
  clone-bases.py --all                         # 克隆全部组合的底座
  clone-bases.py --for-base <名>               # 只克隆用该底座的组合涉及的底座
  clone-bases.py --all --collect-params dist/bases_params   # 并收集 params.json（打包烘焙）
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

BRIDGE = Path(__file__).resolve().parent.parent.parent  # .github/scripts/ → 桥根
# N1：BASE_CACHE 单一真源在 bridge.combos，共享导入（不双写）
sys.path.insert(0, str(BRIDGE))
from bridge.combos import BASE_CACHE  # noqa: E402  （脚本级导入，路径先于导入）


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--for-base", help="只克隆涉及该底座的组合")
    ap.add_argument(
        "--collect-params",
        metavar="DIR",
        help="把各底座钉 version 的 params.json 拷到 DIR（spec 烘焙用）",
    )
    args = ap.parse_args()

    data = yaml.safe_load((BRIDGE / "combos.yaml").read_text(encoding="utf-8"))
    combos = data["combos"]
    bases = data.get("bases", {})

    affected: set[str] = set()
    if args.for_base:
        affected = {
            name
            for name, c in combos.items()
            if args.for_base in {u["source"] for _, u in c["units"].items()}
        }
        if not affected:
            # 无组合使用该底座 = 合法状态（如 bases 注册备用的底座）——无需 clone/检查，
            # 警告并干净退出，避免 check-drift 因「无关底座信号」失败
            print(f"⚠️ 无组合使用底座 {args.for_base}——跳过（无需 clone/检查）")
            return 0
        sources = {
            u["source"] for name in affected for _, u in combos[name]["units"].items()
        }
    elif args.all:
        sources = {u["source"] for c in combos.values() for _, u in c["units"].items()}
    else:
        ap.error("--all 或 --for-base 必给一个")

    for src in sorted(sources):
        dest = BASE_CACHE / src
        if not (dest / ".git").exists():
            url = bases.get(src)
            if not url:
                raise SystemExit(f"❌ combos.yaml bases 未配置「{src}」的 git 地址")
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"↻ 克隆 {url} → {dest}")
            # 普通全量克隆（底座仓小）：`--filter=blob:none` 是部分克隆非浅克隆，
            # 对之 `fetch --unshallow` 会报 128；且全量克隆让 check 的 `git show` 不依赖懒加载
            subprocess.run(["git", "clone", url, str(dest)], check=True)
        print(f"✓ 底座已就绪: {src}")

    # 烘焙：把 combos.yaml units 钉 version 的 params.json 拷出（每底座一份）
    if args.collect_params:
        out = Path(args.collect_params)
        out.mkdir(parents=True, exist_ok=True)
        seen: set[str] = set()
        for name, c in combos.items():
            for _, unit in c["units"].items():
                src = unit["source"]
                if src in seen or src not in sources:
                    continue
                if src in seen:
                    continue
                seen.add(src)
                repo = BASE_CACHE / src
                # 烘焙必须 = combos.yaml 钉 version 的 params.json：总是 checkout 到钉 version
                ver = unit.get("version")
                if ver:
                    subprocess.run(
                        ["git", "-C", str(repo), "checkout", ver],
                        check=True,
                        capture_output=True,
                    )
                src_json = repo / "params.json"
                if not src_json.exists():
                    raise SystemExit(f"❌ {src} 无 params.json（{src_json}）")
                dst = out / f"{src}.json"
                shutil.copy2(src_json, dst)
                print(f"◈ 烘焙 {src}.json ← {src_json}（version {ver}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

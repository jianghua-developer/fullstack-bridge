#!/usr/bin/env python3
"""check.py — fullstack-bridge 检查链：底座 params.json ↔ 组合契约模板 ↔ 契约覆盖。

数据源：
  - combos.yaml：组合 → 前端/后端（source + version 基线）→ 契约模板目录
  - 底座本地兄弟目录（../<source>）：pinned params.json（git show <version>）vs 当前

用法：
  check.py --combo python-react              # 单组合检查（手动 / 桥 CI gate）
  check.py --all                             # 全部组合
  check.py --base-repo <名> --base-version <sha>   # 漂移检查（check-drift workflow 用：
                                            #   载荷携带 base 信号版本，与各组合 pinned 对比）
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

from bridge import BRIDGE
from bridge.combos import load_combos, resolve_base


def read_params(base_dir: Path, ref: str | None) -> tuple[dict | None, str | None]:
    """读底座 params.json：ref 给定时 git show <ref>:params.json，否则工作树文件。"""
    if ref:
        out = subprocess.run(
            ["git", "-C", str(base_dir), "show", f"{ref}:params.json"],
            capture_output=True, text=True,
        )
        if out.returncode != 0:
            return None, f"git show {ref}:params.json 失败: {out.stderr.strip()}"
        return json.loads(out.stdout), None
    p = base_dir / "params.json"
    if not p.exists():
        return None, f"缺少 {p}"
    return json.loads(p.read_text(encoding="utf-8")), None


def enabled_choices(spec: dict) -> list:
    return [c["value"] for c in spec.get("choices", []) if not c.get("disabled")]


def diff_params(old: dict, new: dict) -> list[str]:
    """params 差异（新增/移除/启用取值/字面默认），返回变更描述。"""
    msgs = []
    op, np = old.get("params", {}), new.get("params", {})
    for name in sorted(set(op) | set(np)):
        if name not in op:
            msgs.append(f"新增参数 {name}")
        elif name not in np:
            msgs.append(f"移除参数 {name}")
        else:
            a, b = op[name], np[name]
            if enabled_choices(a) != enabled_choices(b):
                msgs.append(f"{name} 启用取值变化: {enabled_choices(a)} → {enabled_choices(b)}")
            if not a.get("derived") and a.get("default") != b.get("default"):
                msgs.append(f"{name} 默认值变化: {a.get('default')!r} → {b.get('default')!r}")
    return msgs


def declared_params(combo_name: str) -> set[str] | None:
    cp = BRIDGE / "combos" / combo_name / "copier.yml"
    if not cp.exists():
        print(f"⚠️ 缺组合契约模板 combos/{combo_name}/copier.yml")
        return None
    data = yaml.safe_load(cp.read_text(encoding="utf-8"))
    return {k for k in data if not k.startswith("_")}


def has_condition_for(text: str, pname: str) -> bool:
    """契约是否条件引用该参数（支持 {{ }} / [[ ]] 两种 envops 标签）。"""
    return bool(re.search(r"(?:if|elif)\s+" + re.escape(pname) + r"\b", text))


def has_else_for(text: str, pname: str) -> bool:
    """参数的条件块（if/elif <pname> → 匹配 endif）内是否带 else。

    标签定界符显式匹配 `{%` 或 `[%`（jinja2 标准 / copier `[[ ]]` envops）：
    不依赖字符类碰巧含 `%` 的隐式行为——否则将来「优化」成严格边界时
    `[% if %]` 支持会静默失效。
    """
    tags = list(re.finditer(r"[{\[]%\s*(if|elif|else|endif)\b([^%\]}]*)", text))
    for i, m in enumerate(tags):
        stmt, rest = m.group(1), m.group(2)
        if stmt in ("if", "elif") and re.search(rf"\b{re.escape(pname)}\b", rest):
            depth = 0
            for m2 in tags[i + 1:]:
                s2 = m2.group(1)
                if s2 == "if":
                    depth += 1
                elif s2 == "endif":
                    if depth == 0:
                        break
                    depth -= 1
                elif s2 == "else" and depth == 0:
                    return True
    return False


def coverage_report(combo_name: str, params: dict, declared: set[str] | None = None) -> tuple[list[str], list[str]]:
    """检查 2：底座 enabled choices vs 契约显式覆盖（启发式扫描）。

    hard     = 启用取值未显式覆盖且无 else 兜底（渲染为空，真缺口）→ 未对齐
    advisory = 启用取值未显式覆盖但经 else 兜底（请确认语义）→ 提示

    只检查契约声明集（combos/<combo>/copier.yml）内的参数——声明集外的底座参数
    （如 python_version / db_dialect / with_taskqueue）契约本就不覆盖，不判缺口。
    """
    cp = BRIDGE / "combos" / combo_name / "CONTRACT.md.jinja"
    if not cp.exists():
        return [f"缺契约模板 {cp}"], []
    text = cp.read_text(encoding="utf-8")
    hard, advisory = [], []
    for pname, spec in sorted(params.items()):
        if declared is not None and pname not in declared:
            continue
        choices = [c["value"] for c in spec.get("choices", []) if not c.get("disabled")]
        if not choices:
            continue
        if not has_condition_for(text, pname):
            hard.append(f"「{pname}」契约未条件引用（启用取值 {choices} 均未处理）")
            continue
        explicit = set(re.findall(
            rf"(?:if|elif)\s+{re.escape(pname)}\s*==\s*['\"]([^'\"]+)['\"]", text))
        has_else = has_else_for(text, pname)
        for v in choices:
            if v in explicit:
                continue
            if has_else:
                advisory.append(f"「{pname}」启用取值「{v}」未显式覆盖（经 else 兜底，请确认语义）")
            else:
                hard.append(f"「{pname}」启用取值「{v}」契约未覆盖（无 else 兜底，渲染为空）")
    return hard, advisory


def main() -> int:
    ap = argparse.ArgumentParser(description="fullstack-bridge 检查链")
    ap.add_argument("--combo", help="检查指定组合")
    ap.add_argument("--all", action="store_true", help="检查全部组合")
    ap.add_argument("--base-repo", help="漂移检查：底座名（check-drift 信号）")
    ap.add_argument("--base-version", help="漂移检查：底座信号版本（commit/tag）")
    args = ap.parse_args()

    combos = load_combos()

    if args.base_repo:
        if not args.base_version:
            ap.error("--base-version 必填（与 --base-repo 配对）")
        targets = {n: c for n, c in combos.items()
                   if c["frontend"]["source"] == args.base_repo or c["backend"]["source"] == args.base_repo}
        if not targets:
            print(f"⚠️ 无组合使用底座 {args.base_repo}")
            return 0
    elif args.combo:
        if args.combo not in combos:
            ap.error(f"未知组合 {args.combo}（可用: {', '.join(combos)}）")
        targets = {args.combo: combos[args.combo]}
    elif args.all:
        targets = combos
    else:
        ap.error("请给 --combo 或 --all（或 --base-repo --base-version）")

    drift = False
    for name, combo in targets.items():
        for end in ("frontend", "backend"):
            src, pinned = combo[end]["source"], combo[end]["version"]
            base_dir = resolve_base(src)
            old, err = read_params(base_dir, pinned)
            if err:
                print(f"✗ [{name} {end}] {err}"); drift = True; continue
            cur_ref = args.base_version if (args.base_repo and src == args.base_repo) else None
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

    print("\n" + ("❌ 存在漂移/未对齐" if drift else "✅ 全部对齐"))
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())

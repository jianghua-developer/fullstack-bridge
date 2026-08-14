#!/usr/bin/env python3
"""integrate.py — fullstack-bridge 整合编排（全 copier，render.py 已退役）。

生成链：任务输入参数 → copier 前端/后端（--trust 执行 _tasks）
                     → 读两端 .copier-answers.yml → 剔除合并（用户参数优先）
                     → 契约 copier 模板（全必填零默认 + StrictUndefined）→ docs/CONTRACT.md
                     → 项目 README copier 模板 → README.md

CLI 两种模式互斥（决策 ⑥）：
  模式 A：integrate.py <combo缩写> <project>
  模式 B：integrate.py <project> --frontend <本地|git> --backend <本地|git>（必须成对）
通用透传：-D key=value（任意底座参数，零桥改动）
"""

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

BRIDGE = Path(__file__).resolve().parent
COMBO_FILE = BRIDGE / "combos.yaml"

# 精选别名 → copier 参数名（显式传入才进 user_params，缺省让底座 copier 默认/answers 兜底）
CURATED_ALIASES = {
    "--description": "project_description",
    "--api-base-url": "api_base_url",
    "--auth-mode": "auth_mode",
    "--with-db": "with_db",
    "--with-redis": "with_redis",
    "--with-child-app": "with_child_app",
    "--child-apps": "child_apps_raw",
    "--api-prefix": "api_prefix",
}


def load_combos() -> dict:
    return yaml.safe_load(COMBO_FILE.read_text(encoding="utf-8"))["combos"]


def resolve_template(source: str) -> str:
    """系列底座名 → ../<name>/template；显式本地路径 / git 地址原样。"""
    if source.startswith(("/", "./", "../")) or "://" in source or source.startswith("git@"):
        return source
    return str(BRIDGE.parent / source / "template")


def run_copier(src: str, dest: Path, data: dict, trust: bool, skip_tasks: bool) -> None:
    cmd = ["copier", "copy", src, str(dest)]
    for k, v in data.items():
        cmd += ["-d", f"{k}={d_value(v)}"]
    cmd += ["--defaults"]
    if trust:
        cmd += ["--trust"]
    if skip_tasks:
        cmd += ["--skip-tasks"]
    print(f"↻ copier copy {src} → {dest}（{len(data)} 参数）")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"❌ copier 失败（退出 {r.returncode}）: {src}")


def d_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    return str(v)


def read_answers(dest_dir: Path) -> dict:
    p = dest_dir / ".copier-answers.yml"
    if not p.exists():
        raise SystemExit(f"❌ 缺少 {p}——前端/后端生成未完成")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {k: v for k, v in data.items() if not str(k).startswith("_")}


def main() -> int:
    p = argparse.ArgumentParser(description="fullstack-bridge 整合（全 copier）")
    p.add_argument("combo", nargs="?", help="组合缩写（与 --frontend/--backend 互斥）")
    p.add_argument("project", help="项目目录（应用名取 basename）")
    p.add_argument("--frontend", help="显式前端模板（本地模板目录 / git 地址）")
    p.add_argument("--backend", help="显式后端模板（本地模板目录 / git 地址）")
    for alias, key in CURATED_ALIASES.items():
        p.add_argument(alias, default=None, help=f"对应底座参数 {key}（缺省用底座默认）")
    p.add_argument("-D", dest="extra", action="append", default=[], metavar="key=value",
                   help="通用参数透传（任意底座参数，零桥改动）")
    p.add_argument("--skip-tasks", action="store_true", help="跳过 copier _tasks（测试用）")
    args = p.parse_args()

    # ── 模式解析：缩写 vs 显式（互斥 + 成对）──
    if args.combo and (args.frontend or args.backend):
        p.error("组合缩写与 --frontend/--backend 互斥，不可同时使用")
    if args.combo is None and (args.frontend is None or args.backend is None):
        p.error("必须给组合缩写，或 --frontend 与 --backend 成对出现")
    if (args.frontend is None) != (args.backend is None):
        p.error("--frontend 与 --backend 必须同时出现")

    combos = load_combos()
    if args.combo:
        if args.combo not in combos:
            p.error(f"未知组合 {args.combo}（可用: {', '.join(combos)}）")
        combo = combos[args.combo]
        front_src = resolve_template(combo["frontend"]["source"])
        back_src = resolve_template(combo["backend"]["source"])
        contract_dir = BRIDGE / "combos" / combo.get("contract", args.combo)
    else:
        # 显式模式：按 (frontend, backend) 匹配注册组合取契约模板
        matched = next((n for n, c in combos.items()
                        if resolve_template(c["frontend"]["source"]) == resolve_template(args.frontend)
                        and resolve_template(c["backend"]["source"]) == resolve_template(args.backend)), None)
        if not matched:
            p.error(f"未注册组合（{args.frontend} + {args.backend}），无契约模板——请先在 combos.yaml 注册")
        front_src, back_src = args.frontend, args.backend
        contract_dir = BRIDGE / "combos" / matched

    # ── 用户参数：精选别名（显式）+ -D 透传 ──
    user_params = {key: getattr(args, alias.lstrip("-").replace("-", "_"))
                   for alias, key in CURATED_ALIASES.items()
                   if getattr(args, alias.lstrip("-").replace("-", "_")) is not None}
    for item in args.extra:
        if "=" not in item:
            p.error(f"无效 -D 参数: {item}（应为 key=value）")
        k, v = item.split("=", 1)
        user_params[k] = v

    project_dir = Path(args.project)
    project_dir.mkdir(parents=True, exist_ok=True)
    project_name = project_dir.name

    front_dir = project_dir / "frontend"
    back_dir = project_dir / "backend"

    # ── ①② 前端/后端 copier：project_name 派生 + 全部用户参数（copier 忽略未声明的 -d 键）──
    front_data = {"project_name": f"{project_name}-frontend", "project_title": project_name, **user_params}
    run_copier(front_src, front_dir, front_data, trust=True, skip_tasks=args.skip_tasks)

    back_data = {"project_name": f"{project_name}-backend", **user_params}
    run_copier(back_src, back_dir, back_data, trust=True, skip_tasks=args.skip_tasks)

    # ── ③ 读 answers → 剔除合并（用户参数优先；原始项目名覆盖 answers 后缀名）──
    front_ans = read_answers(front_dir)
    back_ans = read_answers(back_dir)
    merged = {**front_ans, **back_ans, **user_params}
    merged["project_name"] = project_name

    # ── ④ 契约 copier 模板 → docs/CONTRACT.md ──
    docs_dir = project_dir / "docs"
    run_copier(str(contract_dir), docs_dir, merged, trust=False, skip_tasks=False)

    # ── ⑤ 项目 README copier 模板 → README.md ──
    readme_tmpl = BRIDGE / "templates" / "project-README"
    run_copier(str(readme_tmpl), project_dir, merged, trust=False, skip_tasks=False)

    print(f"\n✅ 项目已生成: {project_dir}")
    print(f"  {front_dir}/        前端（名 {project_name}-frontend）")
    print(f"  {back_dir}/         后端（名 {project_name}-backend）")
    print(f"  {docs_dir}/CONTRACT.md  前后端契约（改动接口前先读它）")
    print(f"  {project_dir}/README.md  入口说明")
    return 0


if __name__ == "__main__":
    sys.exit(main())

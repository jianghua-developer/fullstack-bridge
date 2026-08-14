#!/usr/bin/env python3
"""integrate.py — fullstack-bridge 整合编排（薄入口；逻辑在 bridge.py 共享库）。

CLI（决策 ⑥）：
  模式 A：integrate.py <combo缩写> <project>
  模式 B：integrate.py <project> --frontend <本地|git> --backend <本地|git>（必须成对，逃生舱）
底座必须是 git 仓（检查链依赖 git 基线）；非 git 本地目录直接拒绝。
通用透传：-D key=value（任意底座参数，零桥改动）
"""

import argparse
import sys
from pathlib import Path

from bridge import BRIDGE
from bridge.answers import merge_answers, read_answers
from bridge.combos import ensure_git_repo, load_combos, resolve_template
from bridge.copier import run_copier

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


def build_parser() -> argparse.ArgumentParser:
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
    return p


def validate_cli(p: argparse.ArgumentParser, args) -> None:
    """CLI 互斥/成对规则（决策 ⑥）。"""
    if args.combo and (args.frontend or args.backend):
        p.error("组合缩写与 --frontend/--backend 互斥，不可同时使用")
    if args.combo is None and (args.frontend is None or args.backend is None):
        p.error("必须给组合缩写，或 --frontend 与 --backend 成对出现")
    if (args.frontend is None) != (args.backend is None):
        p.error("--frontend 与 --backend 必须同时出现")


def resolve_pipeline(p: argparse.ArgumentParser, args, combos: dict) -> tuple[str, str, Path, dict]:
    """组合解析（模式 A/B）→ (前端模板, 后端模板, 契约模板目录, stack 元数据)；底座须 git 仓。"""
    if args.combo:
        if args.combo not in combos:
            p.error(f"未知组合 {args.combo}（可用: {', '.join(combos)}）")
        combo = combos[args.combo]
        front_src = resolve_template(combo["frontend"]["source"])
        back_src = resolve_template(combo["backend"]["source"])
        contract_dir = BRIDGE / "combos" / combo.get("contract", args.combo)
        stack = combo.get("stack", {})
        ensure_git_repo(combo["frontend"]["source"])
        ensure_git_repo(combo["backend"]["source"])
    else:
        # 显式模式（逃生舱）：按 (frontend, backend) 匹配注册组合取契约模板；治理属注册组合
        matched = next((n for n, c in combos.items()
                        if resolve_template(c["frontend"]["source"]) == resolve_template(args.frontend)
                        and resolve_template(c["backend"]["source"]) == resolve_template(args.backend)), None)
        if not matched:
            p.error(f"未注册组合（{args.frontend} + {args.backend}），无契约模板——请先在 combos.yaml 注册")
        front_src, back_src = args.frontend, args.backend
        contract_dir = BRIDGE / "combos" / matched
        stack = combos[matched].get("stack", {})
        ensure_git_repo(args.frontend)
        ensure_git_repo(args.backend)
    return front_src, back_src, contract_dir, stack


def collect_user_params(p: argparse.ArgumentParser, args) -> dict:
    """精选别名（显式传入）+ -D 透传 → 用户参数。"""
    params = {key: getattr(args, alias.lstrip("-").replace("-", "_"))
              for alias, key in CURATED_ALIASES.items()
              if getattr(args, alias.lstrip("-").replace("-", "_")) is not None}
    for item in args.extra:
        if "=" not in item:
            p.error(f"无效 -D 参数: {item}（应为 key=value）")
        k, v = item.split("=", 1)
        params[k] = v
    return params


def generate(project_dir: Path, project_name: str, user_params: dict,
             front_src: str, back_src: str, contract_dir: Path, stack: dict, skip_tasks: bool) -> None:
    """生成链：前端/后端 copier → 读 answers 剔除合并 → 契约/README copier。"""
    front_dir, back_dir, docs_dir = project_dir / "frontend", project_dir / "backend", project_dir / "docs"

    front_data = {"project_name": f"{project_name}-frontend", "project_title": project_name, **user_params}
    run_copier(front_src, front_dir, front_data, trust=True, skip_tasks=skip_tasks)

    back_data = {"project_name": f"{project_name}-backend", **user_params}
    run_copier(back_src, back_dir, back_data, trust=True, skip_tasks=skip_tasks)

    front_ans = read_answers(front_dir)
    back_ans = read_answers(back_dir)
    merged = merge_answers(front_ans, back_ans, user_params, project_name)

    run_copier(str(contract_dir), docs_dir, merged, trust=False, skip_tasks=False)
    # README 数据 = 生成 answers 合并 + combos.yaml 的 stack 元数据（组合专属技术栈）
    run_copier(str(BRIDGE / "templates" / "project-README"), project_dir, {**merged, **stack},
               trust=False, skip_tasks=False)


def main() -> int:
    p = build_parser()
    args = p.parse_args()
    validate_cli(p, args)

    combos = load_combos()
    front_src, back_src, contract_dir, stack = resolve_pipeline(p, args, combos)
    user_params = collect_user_params(p, args)

    project_dir = Path(args.project)
    project_dir.mkdir(parents=True, exist_ok=True)
    generate(project_dir, project_dir.name, user_params, front_src, back_src, contract_dir, stack, args.skip_tasks)

    print(f"\n✅ 项目已生成: {project_dir}")
    print(f"  {project_dir}/frontend/        前端（名 {project_dir.name}-frontend）")
    print(f"  {project_dir}/backend/         后端（名 {project_dir.name}-backend）")
    print(f"  {project_dir}/docs/CONTRACT.md  前后端契约（改动接口前先读它）")
    print(f"  {project_dir}/README.md        入口说明")
    return 0


if __name__ == "__main__":
    sys.exit(main())

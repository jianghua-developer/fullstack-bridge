#!/usr/bin/env python3
"""fullstack-bridge 统一 CLI（Click）：generate + check。

命令树（refactor-step-design §3）：
  bridge generate <combo> <project> [选项…]    # combo 为 generate group 的动态子命令
  bridge check [--combo | --all | --base-repo --base-version]

设计要点：
- 选项 schema 由各 unit 的 params.json 数据驱动（读钉 version 的底座 clone/烘焙），
  不再有 -D 自由透传与精选别名（问题⑦定案）；
- 底座一律 clone/baked（combos.yaml version），无源码兄弟目录模式；
- project_name = project 位置参数 basename（内部派生，非用户选项）。

用法：
  python cli.py generate python-react my-app --auth-mode opaque --with-child-app true
  python cli.py check --combo python-react
"""

from pathlib import Path

import click

from bridge import BRIDGE
from bridge.combos import (
    iter_units,
    load_combos,
    merge_order,
    param_schema,
    resolve_template,
)
from bridge.integrate.answers import merge_answers_by, read_answers
from bridge.integrate.copier import run_copier

# 内部注入、不暴露为用户选项的参数（派生自 project 或生成链）
_INTERNAL_PARAMS = {"project_name", "project_title"}

_TYPE_MAP = {"bool": bool, "int": int}


def _spec_to_click(name: str, spec: dict) -> click.Option:
    """按 params.json spec 生成 click.Option。

    - 有 choices → click.Choice（只列 enabled，禁用取值不暴露）；
    - 无 choices → 按 type 映射（bool/int 强类型；copier 吃字符串由底层转）。
    """
    ptype = spec.get("type", "str")
    opts = [o["value"] for o in spec.get("choices", []) if not o.get("disabled")]
    kwargs: dict = {"default": spec.get("default"), "show_default": True}
    if opts:
        kwargs["type"] = click.Choice(opts)
    elif ptype in _TYPE_MAP:
        kwargs["type"] = _TYPE_MAP[ptype]
    return click.Option([f"--{name.replace('_', '-')}"], **kwargs)


def _build_generate_group() -> click.Group:
    """为每个注册 combo 动态建 generate 子命令（选项 = 该 combo schema）。"""
    group = click.Group("generate", help="生成组合项目：<combo> <project> [选项…]")
    combos = load_combos()

    def make_cmd(combo_name: str, cdef: dict):
        schema = param_schema(combo_name, cdef)
        params: list = [click.Argument(["project"])]
        for pname, spec in sorted(schema.items()):
            if pname in _INTERNAL_PARAMS:
                continue
            params.append(_spec_to_click(pname, spec))

        params.append(
            click.Option(
                ["--skip-tasks"], is_flag=True, help="跳过 copier _tasks（测试用）"
            )
        )

        def callback(project, skip_tasks, **kwargs):
            _do_generate(combo_name, cdef, Path(project), kwargs, skip_tasks)

        cmd = click.Command(
            name=combo_name,
            params=params,
            callback=callback,
            help=f"生成 {combo_name} 组合项目",
        )
        return cmd

    for name, cdef in combos.items():
        group.add_command(make_cmd(name, cdef))
    return group


def _do_generate(
    combo_name: str,
    cdef: dict,
    project_dir: Path,
    user_params: dict,
    skip_tasks: bool = False,
) -> None:
    """生成链：各 unit clone+checkout → copier → answers 合并 → 契约/README。"""
    order = merge_order(cdef)
    answers_by_key: dict[str, dict] = {}
    project_name = project_dir.name

    for key, unit in iter_units(cdef):
        src = resolve_template(unit["source"], unit.get("version"))
        dest = project_dir / key
        data = {
            "project_name": f"{project_name}-{key}",
            "project_title": project_name,
            **user_params,
        }
        run_copier(src, dest, data, trust=True, skip_tasks=skip_tasks)
        answers_by_key[key] = read_answers(dest)

    merged = merge_answers_by(answers_by_key, order, user_params, project_name)

    # 契约渲染至 docs/
    contract_dir = BRIDGE / "combos" / combo_name
    run_copier(
        str(contract_dir), project_dir / "docs", merged, trust=False, skip_tasks=False
    )
    # 项目 README 渲染（units 展示元数据来自 combos.yaml units.{key}.{app,stack}）
    units_desc = [
        {"key": key, "app": unit.get("app", ""), "stack": unit.get("stack", "")}
        for key, unit in iter_units(cdef)
    ]
    run_copier(
        str(BRIDGE / "templates" / "project-README"),
        project_dir,
        {**merged, "units_desc": units_desc},
        trust=False,
        skip_tasks=False,
    )

    print(f"\n✅ 项目已生成: {project_dir}")
    for key, _ in iter_units(cdef):
        print(f"  {project_dir}/{key}/      单元 {key}")
    print(f"  {project_dir}/docs/CONTRACT.md  契约")
    print(f"  {project_dir}/README.md        入口说明")


# ── check 子命令（桥 check 逻辑迁入 Click，沿 units/edges）─────────


def check_combo(
    name: str, combo: dict, base_repo: str | None, base_version: str | None
) -> bool:
    """检查单个组合（漂移/子集/覆盖）。逻辑沿 units/edges。"""
    drift = _check_drift(name, combo, base_repo, base_version)
    declared = _declared_or_warn(name)
    if declared is None:
        return True
    union = _union_params(combo)
    drift |= _check_subset(name, union, declared)
    drift |= _check_coverage(name, union, declared)
    return drift


def _declared_or_warn(combo_name: str) -> set[str] | None:
    from bridge.combos import declared_params

    return declared_params(combo_name)


def _check_drift(
    name: str, combo: dict, base_repo: str | None, base_version: str | None
) -> bool:
    from bridge.check.params import diff_params, read_params
    from bridge.combos import resolve_base

    drift = False
    for key, unit in iter_units(combo):
        src, pinned = unit["source"], unit.get("version")
        base_dir = resolve_base(src)
        old, err = read_params(base_dir, pinned)
        if err:
            print(f"✗ [{name} {key}] {err}")
            drift = True
            continue
        cur_ref = base_version if (base_repo and src == base_repo) else None
        new, err = read_params(base_dir, cur_ref)
        if err:
            print(f"✗ [{name} {key}] {err}")
            drift = True
            continue
        diffs = diff_params(old, new)
        who = f"信号版本 {cur_ref}" if cur_ref else "当前工作树"
        if diffs:
            print(f"⚠️ [{name} {key}] 底座 {src} 漂移（基线 {pinned} vs {who}）:")
            for d in diffs:
                print(f"    - {d}")
            drift = True
        else:
            print(f"✓ [{name} {key}] {src} 对齐基线 {pinned}")
    return drift


def _union_params(combo: dict) -> dict:
    from bridge.check.params import read_params
    from bridge.combos import resolve_base

    union = {}
    for _, unit in iter_units(combo):
        cur, _ = read_params(resolve_base(unit["source"]), None)
        if cur:
            union.update(cur.get("params", {}))
    return union


def _check_subset(name: str, union_params: dict, declared: set[str] | None) -> bool:
    if declared is None:
        return False
    missing = declared - set(union_params)
    if missing:
        print(
            f"⚠️ [{name}] 契约声明参数不在底座参数并集（可能版本未对齐）: {sorted(missing)}"
        )
        return True
    print(f"✓ [{name}] 契约声明参数 ⊆ 底座参数并集")
    return False


def _check_coverage(name: str, union_params: dict, declared: set[str] | None) -> bool:
    from bridge.check.coverage import coverage_report

    drift = False
    hard, advisory = coverage_report(name, union_params, declared)
    for msg in hard:
        print(f"⚠️ [{name}] 检查2 未覆盖: {msg}")
        drift = True
    for msg in advisory:
        print(f"ℹ️ [{name}] 检查2 提示: {msg}")
    return drift


def _select_targets(
    combo_arg: str | None,
    all_flag: bool,
    base_repo: str | None,
    base_version: str | None,
) -> dict:
    combos = load_combos()
    if base_repo:
        if not base_version:
            raise click.UsageError("--base-version 必填（与 --base-repo 配对）")
        targets = {
            n: c
            for n, c in combos.items()
            if base_repo in {u["source"] for _, u in iter_units(c)}
        }
        if not targets:
            print(f"⚠️ 无组合使用底座 {base_repo}")
        return targets
    if combo_arg:
        if combo_arg not in combos:
            raise click.UsageError(f"未知组合 {combo_arg}（可用: {', '.join(combos)}）")
        return {combo_arg: combos[combo_arg]}
    if all_flag:
        return combos
    raise click.UsageError("请给 --combo 或 --all（或 --base-repo --base-version）")


def build_bridge_group() -> click.Group:
    """组装顶层 bridge group（generate 动态子命令 + check）。惰性：import cli 无副作用。"""
    group = click.Group("bridge", help="fullstack-bridge：多单元组合生成 + 对齐检查")
    group.add_command(_build_generate_group())
    group.add_command(_build_check_command())
    return group


def _build_check_command() -> click.Command:
    @click.command("check")
    @click.option("--combo")
    @click.option("--all", "all_flag", is_flag=True, help="检查全部组合")
    @click.option("--base-repo", help="漂移检查：底座名（check-drift 信号）")
    @click.option("--base-version", help="漂移检查：底座信号版本（commit/tag）")
    def check(combo, all_flag, base_repo, base_version):
        """多端对齐/漂移检查。"""
        targets = _select_targets(combo, all_flag, base_repo, base_version)
        if not targets:
            return 0
        drift = False
        for name, cdef in targets.items():
            if check_combo(name, cdef, base_repo, base_version):
                drift = True
        print("\n" + ("❌ 存在漂移/未对齐" if drift else "✅ 全部对齐"))
        return 1 if drift else 0

    return check


def main() -> None:
    build_bridge_group()()


if __name__ == "__main__":
    main()

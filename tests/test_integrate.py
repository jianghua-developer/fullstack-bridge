"""cli.py 单元测试：Click group 结构 + generate schema 选项。"""

import pytest
from click.testing import CliRunner

from cli import _build_generate_group, build_bridge_group
from bridge.combos import load_combos


def test_bridge_group_has_generate_and_check():
    group = build_bridge_group()
    names = set(group.commands)
    assert {"generate", "check"} <= names


def test_generate_group_has_combo_subcommands():
    group = _build_generate_group()
    assert set(group.commands) == set(load_combos())


def test_generate_combo_option_schema():
    """python-react 子命令选项 = 底座 params.json schema（数据驱动）。"""
    group = _build_generate_group()
    cmd = group.commands["python-react"]
    opt_names = {p.name for p in cmd.params}
    assert "project" in opt_names          # 位置参数
    assert "auth_mode" in opt_names         # 原生参数（共享）暴露
    assert "child_apps_raw" in opt_names    # 派生参数输入（原生）暴露
    assert "child_apps" not in opt_names    # 纯派生值不暴露
    assert "project_name" not in opt_names  # 内部派生不暴露
    assert "skip_tasks" in opt_names


def test_generate_help_smoke():
    """--help 不报错（schema 已读底座 params.json）。"""
    runner = CliRunner()
    group = build_bridge_group()
    res = runner.invoke(group, ["generate", "python-react", "--help"])
    assert res.exit_code == 0
    assert "PROJECT" in res.output


def test_generate_unknown_combo():
    group = build_bridge_group()
    # 未知 combo 无子命令 → click 报 no such command
    assert "nope" not in group.commands["generate"].commands

"""cli.py 单元测试：Click group 结构 + generate schema 选项（惰性构建）。"""

import click
import pytest
from click.testing import CliRunner

from cli import _build_generate_group, build_bridge_group
from bridge.combos import load_combos


def _get_combo_cmd(group, name):
    """惰性组：经 get_command 触发构建（需 ctx）。"""
    return group.get_command(click.Context(group), name)


def test_bridge_group_has_generate_and_check():
    group = build_bridge_group()
    names = set(group.commands)
    assert {"generate", "check"} <= names


def test_generate_group_lists_all_combos():
    """list_commands（不触网）列出全部注册组合。"""
    group = _build_generate_group()
    assert set(group.list_commands(click.Context(group))) == set(load_combos())


def test_generate_combo_option_schema():
    """python-react 子命令选项 = 底座 params.json schema（数据驱动，惰性构建）。"""
    group = _build_generate_group()
    cmd = _get_combo_cmd(group, "python-react")
    assert cmd is not None
    opt_names = {p.name for p in cmd.params}
    assert "project" in opt_names  # 位置参数
    assert "auth_mode" in opt_names  # 原生参数（共享）暴露
    assert "child_apps_raw" in opt_names  # 派生参数输入（原生）暴露
    assert "child_apps" not in opt_names  # 纯派生值不暴露
    assert "project_name" not in opt_names  # 内部派生不暴露
    assert "skip_tasks" in opt_names


def test_generate_broken_combo_reports_clear_error(monkeypatch):
    """坏 combo（schema 构建失败）→ UsageError（已注册可辨，S2），不再静默降级 None。"""
    import cli as cli_mod

    def _boom(*a, **k):
        raise SystemExit("❌ 模拟 schema 失败")

    monkeypatch.setattr(cli_mod, "param_schema", _boom)
    group = _build_generate_group()
    with pytest.raises(click.UsageError) as ei:
        group.get_command(click.Context(group), "python-react")
    assert "已注册但 schema 构建失败" in str(ei.value)
    assert "python-react" not in group.commands  # 坏命令不缓存
    # 未注册 combo 仍返回 None（no-such-command，两类错误面区分）
    assert group.get_command(click.Context(group), "nope") is None


def test_generate_help_smoke():
    """--help 不报错且不触发 schema（零触网）。"""
    runner = CliRunner()
    group = build_bridge_group()
    res = runner.invoke(group, ["generate", "--help"])
    assert res.exit_code == 0
    assert "python-react" in res.output


def test_check_help_smoke():
    """check --help 不触发 generate schema（B2：check 路径零触网）。"""
    runner = CliRunner()
    group = build_bridge_group()
    res = runner.invoke(group, ["check", "--help"])
    assert res.exit_code == 0
    assert "combo" in res.output

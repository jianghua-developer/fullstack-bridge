"""list-combos / show-combo 内省 + selection 合并测试。

- 合并 selection = 各 unit 底座 params.json selection 并集 + combo 段（DESIGN §8）；
- show-combo 参数基线：原生（provider 合并）/ 派生只读分列；
- combo 段 selection 结构门（check 全量、generate 单目标共用 validate_combo）。
"""

import json

import pytest
from click.testing import CliRunner

import bridge.combos as combos_mod
from bridge.combos import merge_selection, validate_combo
from cli import build_bridge_group

_SRC_FE = "vite-react-spa-template"
_SRC_BE = "python-fastapi-template"


def _invoke(*args) -> str:
    r = CliRunner().invoke(build_bridge_group(), list(args))
    assert r.exit_code == 0, f"cli 失败:\n{r.output}"
    return r.output


def test_list_combos_json_shape():
    rows = json.loads(_invoke("list-combos", "--json"))
    names = {row["combo"] for row in rows}
    assert "python-react" in names
    row = next(x for x in rows if x["combo"] == "python-react")
    assert [u["key"] for u in row["units"]] == ["frontend", "backend"]
    assert row["edges"] == [["frontend", "backend"]]
    # 合并 selection：底座 selection（react/fastapi）+ combo 段（一体交付）都在
    sel = row["selection"]
    assert sel and sel.get("suited_for")
    assert any("中后台" in s for s in sel["suited_for"])
    assert any("一体交付" in s for s in sel["suited_for"])


def test_show_combo_json_params_and_selection():
    out = _invoke("show-combo", "python-react", "--json")
    d = json.loads(out)
    assert d["combo"] == "python-react"
    assert "auth_mode" in d["params"]  # 原生参数（backend provider 持契约）
    assert "child_apps" not in d["params"]  # 派生不暴露
    assert "child_apps" in d["derived"]  # 派生只读列
    # S1：params 面与 generate 可接受面同构——内部身份参数剔除并标注
    assert "project_name" not in d["params"]
    assert "project_title" not in d["params"]
    assert d["internal"] == ["project_name", "project_title"]
    assert d["selection"]["suited_for"]


def test_show_combo_params_equals_generate_options():
    """show-combo params 键集 == generate 该组合可接受选项键集（内省面即落参面，S1）。"""
    import click

    group = build_bridge_group()
    gen_group = group.commands["generate"]
    ctx = click.Context(gen_group)
    cmd = gen_group.get_command(ctx, "python-react")
    gen_opts = {p.name for p in cmd.params if isinstance(p, click.Option)} - {
        "skip_tasks"
    }
    d = json.loads(_invoke("show-combo", "python-react", "--json"))
    assert set(d["params"]) == gen_opts
    assert "project_name" not in gen_opts  # 内部参数不进 generate 选项面


def test_show_combo_unknown_raises():
    r = CliRunner().invoke(build_bridge_group(), ["show-combo", "nope"])
    assert r.exit_code != 0
    assert "未知组合" in r.output


def test_generate_registered_but_broken_schema_clear_error(monkeypatch):
    """S2：已注册 combo 但 schema 构建失败 → 明确报错，而非误导性 no-such-command。"""
    import cli as cli_mod

    def boom(combo_name, cdef):
        raise SystemExit("模拟缺底座 params.json")

    monkeypatch.setattr(cli_mod, "param_schema", boom)
    r = CliRunner().invoke(
        build_bridge_group(), ["generate", "python-react", "proj", "--skip-tasks"]
    )
    assert r.exit_code != 0
    assert "已注册但 schema 构建失败" in r.output
    assert "No such command" not in r.output


# ── combo 段 selection 结构门 ──────────────────────────────────


def _two_unit_combo(**over):
    base = {
        "units": {"a": {"source": _SRC_FE}, "b": {"source": _SRC_BE}},
        "edges": [["a", "b"]],
    }
    base.update(over)
    return base


def test_validate_combo_ok_without_combo_selection():
    validate_combo("ok", _two_unit_combo())  # combo 段缺省合法


def test_validate_combo_ok_with_combo_selection():
    validate_combo(
        "ok", _two_unit_combo(selection={"suited_for": ["x"], "tradeoffs": ["y"]})
    )


def test_validate_combo_rejects_nonlist_selection():
    with pytest.raises(SystemExit):
        validate_combo("bad", _two_unit_combo(selection={"suited_for": "不是数组"}))


def test_validate_combo_rejects_unknown_selection_field():
    with pytest.raises(SystemExit):
        validate_combo(
            "bad", _two_unit_combo(selection={"suited_for": ["x"], "foo": 1})
        )


# ── merge_selection 纯逻辑（monkeypatch 掉底座读取）─────────────


def _fake_docs(base_doc: dict, combo_doc: dict):
    def fake(source: str, version=None):
        return combo_doc if source == _SRC_BE else base_doc

    return fake


def test_merge_selection_base_union_then_combo_dedup(monkeypatch):
    """各 unit 底座 selection 并集在前，combo 段叠于后；跨源重复去重。"""
    monkeypatch.setattr(
        combos_mod,
        "_unit_params_doc",
        _fake_docs(
            {"selection": {"suited_for": ["A", "B"]}},
            {"selection": {"suited_for": ["C"]}},
        ),
    )
    c = _two_unit_combo(selection={"suited_for": ["B", "D"], "tradeoffs": ["T"]})
    sel = merge_selection(c)
    assert sel["suited_for"] == ["A", "B", "C", "D"]  # B 重复去重、声明序保留
    assert sel["tradeoffs"] == ["T"]


def test_merge_selection_none_when_no_curation(monkeypatch):
    """底座无 selection 且 combo 段缺省 → None（菜单行无 selection）。"""
    monkeypatch.setattr(
        combos_mod, "_unit_params_doc", lambda src, version=None: {"params": {}}
    )
    assert merge_selection(_two_unit_combo()) is None

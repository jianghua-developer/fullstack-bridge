"""bridge.combos 单元测试（units/edges/merge_order/形态校验/统一 clone）。"""

import pytest

from bridge.combos import (
    edge_pairs,
    iter_units,
    load_combos,
    merge_order,
    param_schema,
    resolve_base,
    resolve_template,
    validate_all_combos,
    validate_combo,
)


def test_iter_units_and_sources():
    c = load_combos()["python-react"]
    units = iter_units(c)
    assert [k for k, _ in units] == ["frontend", "backend"]
    assert {u["source"] for _, u in units} == {
        "vite-react-spa-template",
        "python-fastapi-template",
    }


def test_edge_pairs_ok():
    c = load_combos()["python-react"]
    assert edge_pairs(c) == [("frontend", "backend")]


def test_edge_pairs_missing_key_raises():
    with pytest.raises(SystemExit):
        edge_pairs({"units": {"frontend": {}}, "edges": [["frontend", "nope"]]})


def test_edge_pairs_multi_edge():
    combo = {
        "units": {"ui": {}, "bff": {}, "api": {}},
        "edges": [["ui", "bff"], ["bff", "api"]],
    }
    assert edge_pairs(combo) == [("ui", "bff"), ("bff", "api")]


def test_merge_order_single_edge():
    c = load_combos()["python-react"]
    assert merge_order(c) == ["frontend", "backend"]


def test_merge_order_multi_edge_dedup_middle():
    combo = {
        "units": {"ui": {}, "bff": {}, "api": {}},
        "edges": [["ui", "bff"], ["bff", "api"]],
    }
    # bff 首现保留（consumer 位），api 最末赢
    assert merge_order(combo) == ["ui", "bff", "api"]


def test_resolve_template_clones_to_cache():
    """裸名底座 → 缓存 clone 的 template/（砍本地模式，非兄弟目录）。"""
    import pathlib

    t = resolve_template("vite-react-spa-template", "0034ec9")
    p = pathlib.Path(t)
    assert p.name == "template"
    assert (p / "copier.yml").exists()


def test_resolve_base_returns_repo_root():
    b = resolve_base("python-fastapi-template", "c73aa7b")
    assert (b / "params.json").exists()


# 构造合法组合（source 用真实注册底座名，避开 R5 source 校验）
_SRC_FE = "vite-react-spa-template"
_SRC_BE = "python-fastapi-template"


def _two_unit(edges):
    return {
        "units": {"frontend": {"source": _SRC_FE}, "backend": {"source": _SRC_BE}},
        "edges": edges,
    }


def test_validate_combo_ok():
    validate_combo("python-react", load_combos()["python-react"])  # 不抛


def test_validate_combo_rejects_single_unit():
    with pytest.raises(SystemExit):
        validate_combo("solo", {"units": {"only": {"source": _SRC_FE}}})


def test_validate_combo_rejects_missing_edges():
    with pytest.raises(SystemExit):
        validate_combo(
            "no-edge", {"units": {"a": {"source": _SRC_FE}, "b": {"source": _SRC_BE}}}
        )


def test_validate_combo_rejects_bad_edge_key():
    with pytest.raises(SystemExit):
        validate_combo("bad", _two_unit([["frontend", "zzz"]]))


def test_validate_combo_rejects_unregistered_source():
    with pytest.raises(SystemExit):
        validate_combo(
            "bad-src",
            {
                "units": {"a": {"source": "not-a-real-base"}, "b": {"source": _SRC_BE}},
                "edges": [["a", "b"]],
            },
        )


def test_validate_combo_rejects_non_chain_edges():
    """edges 数 ≠ units-1（如 3 单元 2 边中 1 边缺失/多出）→ 拒绝。"""
    with pytest.raises(SystemExit):
        validate_combo(
            "bad-chain",
            {
                "units": {
                    "a": {"source": _SRC_FE},
                    "b": {"source": _SRC_BE},
                    "c": {"source": _SRC_FE},
                },
                "edges": [["a", "b"]],
            },
        )  # 3 单元应 2 边


def test_validate_combo_ok_chain_three_units():
    """3 单元 2 边链合法（ui-bff-api 形态）。"""
    validate_combo(
        "chain3",
        {
            "units": {
                "a": {"source": _SRC_FE},
                "b": {"source": _SRC_BE},
                "c": {"source": _SRC_FE},
            },
            "edges": [["a", "b"], ["b", "c"]],
        },
    )


def test_validate_all_combos_registered():
    validate_all_combos()  # 注册组合应全部通过形态校验


def test_param_schema_exposes_native_hides_derived():
    """暴露 derived:false（含 child_apps_raw），隐藏 derived:true（child_apps）。"""
    c = load_combos()["python-react"]
    schema = param_schema("python-react", c)
    assert "auth_mode" in schema
    assert "child_apps_raw" in schema  # 派生输入是原生参数 → 暴露
    assert "child_apps" not in schema  # 纯派生值 → 不暴露
    assert (
        "project_name" not in schema
        or schema["project_name"].get("unit_key") == "frontend"
    )

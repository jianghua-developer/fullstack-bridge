"""bridge.combos 单元测试（units/edges/merge_order/统一 clone）。"""

import pytest

from bridge.combos import (edge_pairs, ensure_git_repo, is_url, iter_units,
                           load_combos, merge_order, param_schema,
                           resolve_base, resolve_template)


def test_is_url():
    assert is_url("git@github.com:jianghua-developer/x.git")
    assert is_url("https://github.com/x/y.git")
    assert not is_url("vite-react-spa-template")
    assert not is_url("/home/jeff/project/x/template")


def test_iter_units_and_sources():
    c = load_combos()["python-react"]
    units = iter_units(c)
    assert [k for k, _ in units] == ["frontend", "backend"]
    assert {u["source"] for _, u in units} == {
        "vite-react-spa-template", "python-fastapi-template"}


def test_edge_pairs_ok():
    c = load_combos()["python-react"]
    assert edge_pairs(c) == [("frontend", "backend")]


def test_edge_pairs_missing_key_raises():
    with pytest.raises(SystemExit):
        edge_pairs({"units": {"frontend": {}}, "edges": [["frontend", "nope"]]})


def test_edge_pairs_multi_edge():
    combo = {"units": {"ui": {}, "bff": {}, "api": {}},
             "edges": [["ui", "bff"], ["bff", "api"]]}
    assert edge_pairs(combo) == [("ui", "bff"), ("bff", "api")]


def test_merge_order_single_edge():
    c = load_combos()["python-react"]
    assert merge_order(c) == ["frontend", "backend"]


def test_merge_order_multi_edge_dedup_middle():
    combo = {"units": {"ui": {}, "bff": {}, "api": {}},
             "edges": [["ui", "bff"], ["bff", "api"]]}
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


def test_resolve_base_url_raises():
    with pytest.raises(ValueError):
        resolve_base("git@github.com:x/y.git")


def test_ensure_git_repo_explicit_local(tmp_path):
    """显式本地路径须为 git 检出；非 git 拒绝。"""
    with pytest.raises(SystemExit):
        ensure_git_repo(str(tmp_path))


def test_param_schema_exposes_native_hides_derived():
    """暴露 derived:false（含 child_apps_raw），隐藏 derived:true（child_apps）。"""
    c = load_combos()["python-react"]
    schema = param_schema("python-react", c)
    assert "auth_mode" in schema
    assert "child_apps_raw" in schema      # 派生输入是原生参数 → 暴露
    assert "child_apps" not in schema      # 纯派生值 → 不暴露
    assert "project_name" not in schema or schema["project_name"].get("unit_key") == "frontend"

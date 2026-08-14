"""bridge.combos 单元测试。"""

import pytest

from bridge import BRIDGE
from bridge.combos import declared_params, is_url, resolve_base, resolve_template


def test_is_url():
    assert is_url("git@github.com:jianghua-developer/x.git")
    assert is_url("https://github.com/x/y.git")
    assert not is_url("vite-react-spa-template")
    assert not is_url("/home/jeff/project/x/template")


def test_resolve_template_bare_name():
    assert resolve_template("vite-react-spa-template") == str(
        BRIDGE.parent / "vite-react-spa-template" / "template")


def test_resolve_template_path_and_url():
    assert resolve_template("/tmp/x/template") == "/tmp/x/template"
    assert resolve_template("git@github.com:jianghua-developer/x.git") == \
        "git@github.com:jianghua-developer/x.git"


def test_resolve_base_bare_name():
    assert resolve_base("python-fastapi-template") == BRIDGE.parent / "python-fastapi-template"


def test_resolve_base_url_raises():
    with pytest.raises(ValueError):
        resolve_base("git@github.com:x/y.git")


def test_declared_params_real_combo():
    """真实组合契约模板的声明参数（决策③ 检查基线）。"""
    declared = declared_params("python-react")
    assert declared is not None
    assert {"auth_mode", "with_db", "api_prefix", "child_apps_raw"} <= declared
    assert all(not k.startswith("_") for k in declared)

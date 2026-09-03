"""bridge.check.params 单元测试：params.json 读取与对比。"""

from bridge.check.params import diff_params, enabled_choices


def test_enabled_choices_filters_disabled():
    spec = {
        "choices": [
            {"value": "none"},
            {"value": "opaque"},
            {"value": "jwt", "disabled": True},
        ]
    }
    assert enabled_choices(spec) == ["none", "opaque"]


def test_diff_params_choice_change():
    old = {
        "params": {"auth_mode": {"choices": [{"value": "none"}, {"value": "opaque"}]}}
    }
    new = {
        "params": {
            "auth_mode": {
                "choices": [{"value": "none"}, {"value": "opaque"}, {"value": "jwt"}]
            }
        }
    }
    diffs = diff_params(old, new)
    assert any("启用取值变化" in d for d in diffs)


def test_diff_params_default_change():
    old = {"params": {"api_base_url": {"default": "/api", "derived": False}}}
    new = {"params": {"api_base_url": {"default": "/foo", "derived": False}}}
    diffs = diff_params(old, new)
    assert any("默认值变化" in d for d in diffs)


def test_diff_params_derived_default_ignored():
    """派生参数默认值变化不报（copier 计算，字面默认无意义）。"""
    old = {"params": {"child_apps": {"default": "expr1", "derived": True}}}
    new = {"params": {"child_apps": {"default": "expr2", "derived": True}}}
    assert diff_params(old, new) == []


def test_diff_params_add_remove():
    old = {"params": {"a": {}, "b": {}}}
    new = {"params": {"a": {}}}
    diffs = diff_params(old, new)
    assert any("移除参数 b" in d for d in diffs)

"""bridge.check.coverage 单元测试：契约取值覆盖扫描。"""

from bridge.check.coverage import coverage_report, has_condition_for, has_else_for


def test_has_condition_for_both_envops():
    assert has_condition_for("{% if auth_mode == 'opaque' %}", "auth_mode")
    assert has_condition_for("[% if auth_mode == 'opaque' %]", "auth_mode")
    assert not has_condition_for("{% if with_db %}", "auth_mode")


def test_has_else_for():
    assert has_else_for("{% if auth_mode == 'opaque' %}a{% else %}b{% endif %}", "auth_mode")
    assert has_else_for("[% if auth_mode == 'opaque' %]a[% else %]b[% endif %]", "auth_mode")
    assert not has_else_for("{% if with_db %}a{% endif %}", "with_db")


def test_coverage_report_real_contract_clean():
    """真实 python-react 契约：auth_mode none/opaque 无硬缺口，none 经 else 兜底提示。"""
    params = {"auth_mode": {"type": "str",
                            "choices": [{"value": "none"}, {"value": "opaque"}]}}
    hard, advisory = coverage_report("python-react", params, declared={"auth_mode"})
    assert hard == []
    assert any("none" in m for m in advisory)


def test_coverage_report_new_choice_advisory():
    """新增启用取值 jwt：契约未显式覆盖 → 经 else 兜底提示（非硬缺口）。"""
    params = {"auth_mode": {"type": "str",
                            "choices": [{"value": "none"}, {"value": "opaque"}, {"value": "jwt"}]}}
    hard, advisory = coverage_report("python-react", params, declared={"auth_mode"})
    assert hard == []
    assert any("jwt" in m for m in advisory)


def test_coverage_report_declared_scope():
    """声明集外参数不判缺口（如 python_version）。"""
    params = {"python_version": {"type": "str",
                                 "choices": [{"value": "3.12"}, {"value": "3.13"}]}}
    hard, advisory = coverage_report("python-react", params, declared={"auth_mode"})
    assert hard == [] and advisory == []

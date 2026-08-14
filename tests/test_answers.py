"""bridge.integrate.answers 单元测试：剔除合并优先级。"""

from bridge.integrate.answers import merge_answers


def test_merge_precedence_backend_over_frontend():
    """优先级：用户 > 后端 > 前端；同名后端覆盖前端。"""
    merged = merge_answers(
        front_ans={"auth_mode": "none", "api_base_url": "/api"},
        back_ans={"auth_mode": "opaque", "api_prefix": "/api/v1"},
        user_params={},
        project_name="demo",
    )
    assert merged["auth_mode"] == "opaque"  # 后端覆盖前端
    assert merged["api_base_url"] == "/api"  # 仅前端有
    assert merged["api_prefix"] == "/api/v1"  # 仅后端有


def test_merge_precedence_user_highest():
    merged = merge_answers(
        {"auth_mode": "none"}, {"auth_mode": "opaque"}, {"auth_mode": "jwt"}, "demo")
    assert merged["auth_mode"] == "jwt"


def test_merge_project_name_original():
    """project_name 始终为原始项目名（覆盖两端后缀名）。"""
    merged = merge_answers(
        {"project_name": "demo-frontend"}, {"project_name": "demo-backend"}, {}, "demo")
    assert merged["project_name"] == "demo"


def test_merge_internal_fields():
    """read_answers 应剔除 _ 前缀内部字段（_src_path 等）。"""
    from pathlib import Path
    import tempfile

    import yaml

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / ".copier-answers.yml"
        p.write_text("_src_path: /tmp/x\nauth_mode: opaque\n", encoding="utf-8")
        from bridge.integrate.answers import read_answers

        ans = read_answers(Path(d))
        assert ans == {"auth_mode": "opaque"}

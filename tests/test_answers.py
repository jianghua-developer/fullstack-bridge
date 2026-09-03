"""bridge.integrate.answers 单元测试：剔除合并优先级。"""

from bridge.integrate.answers import merge_answers, merge_answers_by


def test_merge_by_order_single_edge():
    """按序合并：consumer→provider，后者赢（= user>backend>frontend）。"""
    merged = merge_answers_by(
        {"frontend": {"auth_mode": "none"}, "backend": {"auth_mode": "opaque"}},
        ["frontend", "backend"], {}, "demo")
    assert merged["auth_mode"] == "opaque"


def test_merge_by_multi_edge_middle_unit():
    """多 edge 链：ui→bff→api；api(最深 provider) 对同名赢，bff 私有参数保留。"""
    merged = merge_answers_by(
        {"ui": {"transport": "browser", "auth_mode": "none"},
         "bff": {"auth_mode": "opaque", "bff_route": "/gw"},
         "api": {"auth_mode": "jwt", "api_only": "/v1"}},
        ["ui", "bff", "api"], {}, "demo")
    assert merged["auth_mode"] == "jwt"       # api（最深 provider）赢
    assert merged["transport"] == "browser"   # ui 私有保留
    assert merged["bff_route"] == "/gw"       # bff 私有保留
    assert merged["api_only"] == "/v1"


def test_merge_by_user_highest():
    merged = merge_answers_by(
        {"frontend": {"auth_mode": "none"}, "backend": {"auth_mode": "opaque"}},
        ["frontend", "backend"], {"auth_mode": "jwt"}, "demo")
    assert merged["auth_mode"] == "jwt"


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

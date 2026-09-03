"""python-react 组合 e2e：cli.py generate 生成并校验产物（--skip-tasks 避免装依赖）。

新增组合（如 python-vue）→ 新建 test_e2e_for_<组合>.py，复用 tests/utils/runner.run_generate。
"""

from utils.runner import run_generate


def test_e2e_opaque_full_for_python_react(tmp_path):
    proj = tmp_path / "test-app"
    run_generate(
        proj,
        "python-react",
        "--auth-mode",
        "opaque",
        "--with-child-app",
        "true",
        "--child-apps-raw",
        "backend,admin:adm",
    )

    assert (proj / "frontend").is_dir()
    assert (proj / "backend").is_dir()

    contract = (proj / "docs" / "CONTRACT.md").read_text(encoding="utf-8")
    assert "/api/v1" in contract  # api_prefix 默认从后端 answers 渲染
    assert "backend" in contract  # child_apps 枚举
    assert "admin" in contract
    assert "{%" not in contract and "{{" not in contract  # 无 jinja 残留

    readme = (proj / "README.md").read_text(encoding="utf-8")
    assert "Vite + React" in readme  # stack 元数据渲染
    assert "FastAPI" in readme


def test_e2e_none_trim_for_python_react(tmp_path):
    proj = tmp_path / "test-app2"
    run_generate(
        proj,
        "python-react",
        "--auth-mode",
        "none",
        "--with-db",
        "false",
        "--with-child-app",
        "false",
    )

    contract = (proj / "docs" / "CONTRACT.md").read_text(encoding="utf-8")
    assert "### 2.4" not in contract  # 认证章节裁剪
    assert "40102" not in contract  # 无认证错误码
    assert "{%" not in contract and "{{" not in contract

"""e2e：integrate.py 生成项目并校验产物（--skip-tasks 避免装依赖）。"""

import subprocess
from pathlib import Path

BRIDGE = Path(__file__).resolve().parent.parent


def run_integrate(project_dir, *extra, combo="python-react"):
    """调用 integrate.py 生成项目；combo 可覆盖（如将来 python-vue 复用）。"""
    cmd = [str(BRIDGE / ".venv" / "bin" / "python"), str(BRIDGE / "integrate.py"),
           combo, str(project_dir), "--skip-tasks", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, f"integrate.py 失败:\n{r.stdout}\n{r.stderr}"
    return r


def test_e2e_opaque_full(tmp_path):
    proj = tmp_path / "test-app"
    run_integrate(proj, "--auth-mode", "opaque", "--with-child-app", "true",
                  "--child-apps", "backend,admin:adm")

    assert (proj / "frontend").is_dir()
    assert (proj / "backend").is_dir()

    contract = (proj / "docs" / "CONTRACT.md").read_text(encoding="utf-8")
    assert "/api/v1" in contract            # api_prefix 默认从后端 answers 渲染
    assert "backend" in contract             # child_apps 枚举
    assert "admin" in contract
    assert "{%" not in contract and "{{" not in contract  # 无 jinja 残留

    readme = (proj / "README.md").read_text(encoding="utf-8")
    assert "Vite + React" in readme          # stack 元数据渲染
    assert "FastAPI" in readme


def test_e2e_none_trim(tmp_path):
    proj = tmp_path / "test-app2"
    run_integrate(proj, "--auth-mode", "none", "--with-db", "false", "--with-child-app", "false")

    contract = (proj / "docs" / "CONTRACT.md").read_text(encoding="utf-8")
    assert "### 2.4" not in contract         # 认证章节裁剪
    assert "40102" not in contract           # 无认证错误码
    assert "{%" not in contract and "{{" not in contract

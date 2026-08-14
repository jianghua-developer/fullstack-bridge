"""e2e 复用工具：integrate.py 调用。"""

import subprocess
from pathlib import Path

# tests/utils/runner.py → 桥根
BRIDGE = Path(__file__).resolve().parent.parent.parent


def run_integrate(project_dir, *extra, combo="python-react"):
    """调用 integrate.py 生成项目；combo 可覆盖（如将来 python-vue）。"""
    cmd = [str(BRIDGE / ".venv" / "bin" / "python"), str(BRIDGE / "integrate.py"),
           combo, str(project_dir), "--skip-tasks", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, f"integrate.py 失败:\n{r.stdout}\n{r.stderr}"
    return r

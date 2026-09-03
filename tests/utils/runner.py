"""e2e 复用工具：统一 CLI（cli.py generate）调用。"""

import subprocess
from pathlib import Path

# tests/utils/runner.py → 桥根
BRIDGE = Path(__file__).resolve().parent.parent.parent


def run_generate(project_dir, combo="python-react", *extra):
    """调用 cli.py generate 生成项目（combo 为子命令）；*extra 为 schema 选项。"""
    cmd = [
        str(BRIDGE / ".venv" / "bin" / "python"),
        str(BRIDGE / "cli.py"),
        "generate",
        combo,
        str(project_dir),
        "--skip-tasks",
        *extra,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, f"cli.py generate 失败:\n{r.stdout}\n{r.stderr}"
    return r


# 向后兼容别名（旧 e2e 仍用 run_integrate 命名）
run_integrate = run_generate

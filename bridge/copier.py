"""copier 执行封装。"""

import subprocess
from pathlib import Path


def d_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    return str(v)


def run_copier(src: str, dest: Path, data: dict, trust: bool, skip_tasks: bool) -> None:
    cmd = ["copier", "copy", src, str(dest)]
    for k, v in data.items():
        cmd += ["-d", f"{k}={d_value(v)}"]
    cmd += ["--defaults"]
    if trust:
        cmd += ["--trust"]
    if skip_tasks:
        cmd += ["--skip-tasks"]
    print(f"↻ copier copy {src} → {dest}（{len(data)} 参数）")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"❌ copier 失败（退出 {r.returncode}）: {src}")

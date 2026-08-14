"""底座 params.json 读取与对比（检查 1 数据层）。"""

import json
import subprocess
from pathlib import Path


def read_params(base_dir: Path, ref: str | None) -> tuple[dict | None, str | None]:
    """读底座 params.json：ref 给定时 git show <ref>:params.json，否则工作树文件。"""
    if ref:
        out = subprocess.run(
            ["git", "-C", str(base_dir), "show", f"{ref}:params.json"],
            capture_output=True, text=True,
        )
        if out.returncode != 0:
            return None, f"git show {ref}:params.json 失败: {out.stderr.strip()}"
        return json.loads(out.stdout), None
    p = base_dir / "params.json"
    if not p.exists():
        return None, f"缺少 {p}"
    return json.loads(p.read_text(encoding="utf-8")), None


def enabled_choices(spec: dict) -> list:
    return [c["value"] for c in spec.get("choices", []) if not c.get("disabled")]


def diff_params(old: dict, new: dict) -> list[str]:
    """params 差异（新增/移除/启用取值/字面默认），返回变更描述。"""
    msgs = []
    op, np = old.get("params", {}), new.get("params", {})
    for name in sorted(set(op) | set(np)):
        if name not in op:
            msgs.append(f"新增参数 {name}")
        elif name not in np:
            msgs.append(f"移除参数 {name}")
        else:
            a, b = op[name], np[name]
            if enabled_choices(a) != enabled_choices(b):
                msgs.append(f"{name} 启用取值变化: {enabled_choices(a)} → {enabled_choices(b)}")
            if not a.get("derived") and a.get("default") != b.get("default"):
                msgs.append(f"{name} 默认值变化: {a.get('default')!r} → {b.get('default')!r}")
    return msgs

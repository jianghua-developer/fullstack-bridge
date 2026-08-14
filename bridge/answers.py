"""answers 读取 + 剔除合并。"""

from pathlib import Path

import yaml


def read_answers(dest_dir: Path) -> dict:
    p = dest_dir / ".copier-answers.yml"
    if not p.exists():
        raise SystemExit(f"❌ 缺少 {p}——前端/后端生成未完成")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {k: v for k, v in data.items() if not str(k).startswith("_")}


def merge_answers(front_ans: dict, back_ans: dict, user_params: dict, project_name: str) -> dict:
    """剔除合并，优先级：**用户参数 > 后端 answers > 前端 answers**。

    后端优先于前端（契约以后端侧为主）；同名冲突时后端覆盖前端。
    project_name 始终为原始项目名（覆盖前端/后端 answers 的后缀名 xxx-frontend / xxx-backend）。
    """
    merged = {**front_ans, **back_ans, **user_params}
    merged["project_name"] = project_name
    return merged

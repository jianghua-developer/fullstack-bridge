"""answers 读取 + 剔除合并。"""

from pathlib import Path

import yaml


def read_answers(dest_dir: Path) -> dict:
    p = dest_dir / ".copier-answers.yml"
    if not p.exists():
        raise SystemExit(f"❌ 缺少 {p}——单元生成未完成")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {k: v for k, v in data.items() if not str(k).startswith("_")}


def merge_answers_by(answers_by_key: dict[str, dict], order: list[str],
                     user_params: dict, project_name: str) -> dict:
    """按序剔除合并：dict.update 依 order，后者（provider/更深）赢。

    order 由 combos.merge_order 提供（consumer→provider 序）；python-react
    [frontend, backend] 序 ≡ 旧 `user > backend > frontend`。
    project_name 始终为原始项目名（覆盖各端后缀名 xxx-frontend / xxx-backend）。
    """
    merged: dict = {}
    for key in order:
        merged.update(answers_by_key.get(key, {}))
    merged.update(user_params)  # 用户参数最高
    merged["project_name"] = project_name
    return merged


def merge_answers(front_ans: dict, back_ans: dict, user_params: dict, project_name: str) -> dict:
    """（兼容层）双端合并：frontend → backend → user。等价 merge_answers_by(front→back)。"""
    return merge_answers_by({"frontend": front_ans, "backend": back_ans},
                            ["frontend", "backend"], user_params, project_name)

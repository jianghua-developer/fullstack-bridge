"""契约取值覆盖扫描（检查 2）。"""

import re

from .. import BRIDGE


def has_condition_for(text: str, pname: str) -> bool:
    """契约是否条件引用该参数（支持 {{ }} / [[ ]] 两种 envops 标签）。"""
    return bool(re.search(r"(?:if|elif)\s+" + re.escape(pname) + r"\b", text))


def has_else_for(text: str, pname: str) -> bool:
    """参数的条件块（if/elif <pname> → 匹配 endif）内是否带 else。

    标签定界符显式匹配 `{%` 或 `[%`（jinja2 标准 / copier `[[ ]]` envops）：
    不依赖字符类碰巧含 `%` 的隐式行为——否则将来「优化」成严格边界时
    `[% if %]` 支持会静默失效。
    """
    tags = list(re.finditer(r"[{\[]%\s*(if|elif|else|endif)\b([^%\]}]*)", text))
    for i, m in enumerate(tags):
        stmt, rest = m.group(1), m.group(2)
        if stmt in ("if", "elif") and re.search(rf"\b{re.escape(pname)}\b", rest):
            depth = 0
            for m2 in tags[i + 1:]:
                s2 = m2.group(1)
                if s2 == "if":
                    depth += 1
                elif s2 == "endif":
                    if depth == 0:
                        break
                    depth -= 1
                elif s2 == "else" and depth == 0:
                    return True
    return False


def coverage_report(combo_name: str, params: dict, declared: set[str] | None = None) -> tuple[list[str], list[str]]:
    """检查 2：底座 enabled choices vs 契约显式覆盖（启发式扫描）。

    hard     = 启用取值未显式覆盖且无 else 兜底（渲染为空，真缺口）→ 未对齐
    advisory = 启用取值未显式覆盖但经 else 兜底（请确认语义）→ 提示

    只检查契约声明集（combos/<combo>/copier.yml）内的参数——声明集外的底座参数
    （如 python_version / db_dialect / with_taskqueue）契约本就不覆盖，不判缺口。
    """
    cp = BRIDGE / "combos" / combo_name / "CONTRACT.md.jinja"
    if not cp.exists():
        return [f"缺契约模板 {cp}"], []
    text = cp.read_text(encoding="utf-8")
    hard, advisory = [], []
    for pname, spec in sorted(params.items()):
        if declared is not None and pname not in declared:
            continue
        choices = [c["value"] for c in spec.get("choices", []) if not c.get("disabled")]
        if not choices:
            continue
        if not has_condition_for(text, pname):
            hard.append(f"「{pname}」契约未条件引用（启用取值 {choices} 均未处理）")
            continue
        explicit = set(re.findall(
            rf"(?:if|elif)\s+{re.escape(pname)}\s*==\s*['\"]([^'\"]+)['\"]", text))
        has_else = has_else_for(text, pname)
        for v in choices:
            if v in explicit:
                continue
            if has_else:
                advisory.append(f"「{pname}」启用取值「{v}」未显式覆盖（经 else 兜底，请确认语义）")
            else:
                hard.append(f"「{pname}」启用取值「{v}」契约未覆盖（无 else 兜底，渲染为空）")
    return hard, advisory

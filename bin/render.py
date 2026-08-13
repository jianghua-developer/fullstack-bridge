#!/usr/bin/env python3
"""fullstack-bridge 模板渲染器：jinja2 渲染 .jinja 模板 → 输出文件。

供整合脚本与人工调用，渲染契约模板与项目 README 模板。
- 使用 StrictUndefined：未提供的变量直接报错，防止静默漏渲染
- 渲染后校验产物不含 {% / {{ / {# 残留，防止条件块泄漏进最终文件
"""

import argparse
from pathlib import Path


def parse_data(items: list[str]) -> dict[str, str]:
    data = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"无效参数: {item}(应为 key=value)")
        key, value = item.split("=", 1)
        data[key] = value
    return data


def render(template_path: str, data: dict[str, str], output_path: str) -> None:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    template = Path(template_path)
    if not template.exists():
        raise SystemExit(f"模板不存在: {template}")

    env = Environment(
        loader=FileSystemLoader(str(template.parent)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    rendered = env.get_template(template.name).render(**data)

    for marker in ("{%", "{{", "{#"):
        if marker in rendered:
            raise SystemExit(
                f"⚠️ 渲染产物仍含 {marker}:存在未处理的条件块/变量，请检查参数是否完整"
            )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"✓ 已写入 {output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="渲染 .jinja 模板（契约 / README），参数以 -d key=value 传入"
    )
    parser.add_argument("template", help="模板文件路径(.jinja)")
    parser.add_argument("-o", "--output", required=True, help="输出文件路径")
    parser.add_argument(
        "-d", "--data", action="append", default=[], help="参数 key=value，可重复"
    )
    args = parser.parse_args()

    data = parse_data(args.data)
    render(args.template, data, args.output)


if __name__ == "__main__":
    main()

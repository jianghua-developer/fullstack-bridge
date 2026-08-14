"""bridge — fullstack-bridge 共享库包。

根目录只放**两条链共用**的模块；生成链 / 检查链各自独立成子包：

- combos.py    通用：组合解析（combos.yaml / 模板/底座解析 / git 校验 / 契约声明参数）
- integrate/   生成链专用：copier 执行、answers 读取合并
- check/       检查链专用：底座 params.json 读取对比（检查 1）、契约覆盖扫描（检查 2）
"""

from pathlib import Path

# fullstack-bridge 仓库根（bridge/ 的上一级）
BRIDGE = Path(__file__).resolve().parent.parent

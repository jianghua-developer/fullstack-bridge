"""bridge — fullstack-bridge 共享库包（单一职责模块）。

- combos.py   组合解析（combos.yaml / 模板/底座解析 / git 校验 / 契约声明参数）
- copier.py   copier 执行封装
- answers.py  answers 读取 + 剔除合并
- params.py   底座 params.json 读取与对比（检查 1 数据层）
- coverage.py 契约取值覆盖扫描（检查 2）
"""

from pathlib import Path

# fullstack-bridge 仓库根（bridge/ 的上一级）
BRIDGE = Path(__file__).resolve().parent.parent

"""bridge — fullstack-bridge 共享库包（单一职责模块）。

- combos.py  组合解析（combos.yaml / 模板/底座解析 / git 校验）
- copier.py  copier 执行封装
- answers.py answers 读取 + 剔除合并
"""

from pathlib import Path

# fullstack-bridge 仓库根（bridge/ 的上一级）
BRIDGE = Path(__file__).resolve().parent.parent

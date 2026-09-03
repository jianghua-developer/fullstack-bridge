# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec：打包统一 CLI（cli.py）为单文件可执行 bridge。
# 依赖：copier 走 API（run_copy）随 Python 打包；桥自身数据（combos.yaml/combos/templates）打进。
# 底座 params.json 烘焙：打包前须先跑 clone-bases.py --collect-params bases_params
#   （克隆底座到缓存 + 收集钉 version 的 params.json）→ 打进包内，frozen 下 schema/help 零网络。
# 底座 template/ 与 check 的 git show 仍需 clone 缓存（生成/漂移对比用）。
# 构建：uv run pyinstaller bridge.spec

import os
from pathlib import Path

# 烘焙目录（CI 先跑 clone-bases --collect-params 生成；本地无则空 datas，schema 走 clone）
_params_dir = Path('bases_params')
_datas = [
    ('combos.yaml', '.'),
    ('combos', 'combos'),
    ('templates', 'templates'),
]
if _params_dir.is_dir():
    _datas.append((str(_params_dir), 'bases_params'))

a = Analysis(
    ['cli.py'],
    pathex=[],
    binaries=[],
    datas=_datas,
    # copier 默认扩展按字符串引用 jinja2_ansible_filters，静态分析漏包 → 显式隐藏导入
    hiddenimports=['jinja2_ansible_filters'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX 压缩需额外工具，非必要
    console=True,
)

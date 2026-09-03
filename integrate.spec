# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec：打包 integrate 为单文件可执行。
# 依赖：copier 走 API（run_copy）随 Python 打包；桥自身数据（combos.yaml/combos/templates）打进。
# 底座为独立 git 仓：frozen 模式运行时克隆到 ~/.cache/fullstack-bridge/bases（按 combos.yaml version）。
# 构建：uv run pyinstaller integrate.spec

a = Analysis(
    ['integrate.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('combos.yaml', '.'),
        ('combos', 'combos'),
        ('templates', 'templates'),
    ],
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
    name='integrate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX 压缩需额外工具，非必要
    console=True,
)

"""copier 执行封装：走 copier Python API（copier.run_copy），非 subprocess 调 CLI。

走 API 是「编译成可执行文件」的前提——copier 作为 Python 依赖被打包进单文件。
"""

from pathlib import Path


def run_copier(src: str, dest: Path, data: dict, trust: bool, skip_tasks: bool) -> None:
    """copier API 复制模板到 dest。

    - trust=True → unsafe=True：我们的模板，等价 CLI `--trust`（允许 _tasks 执行）
    - skip_tasks=True → 跳过 _tasks（测试用，避免装依赖）
    - data 值类型直传（bool/str 等），copier 按模板 question 类型解析
    """
    import copier  # 延迟导入：copier 是运行时依赖（打包进单文件）

    print(f"↻ copier copy {src} → {dest}（{len(data)} 参数）")
    try:
        copier.run_copy(
            src_path=src,
            dst_path=dest,
            data=data,
            defaults=True,
            quiet=False,
            unsafe=trust,
            skip_tasks=skip_tasks,
        )
    except Exception as e:  # noqa: BLE001 - 统一转为退出信息
        raise SystemExit(f"❌ copier 失败: {e}") from e

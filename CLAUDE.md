# fullstack-bridge · 前后端连通层

本项目是 AI Foundation 系列的多端连通层：把单端底座按 **units/edges 组合**（N≥2）与契约整合成前后端一体大目录，供 AI 生成完整业务系统时各端共同对照同一份契约。

系列元信息（系列目的 / 总体设计思路 / 当前状态 / 姊妹底座位置 / copier 位置）由下方共享文件导入，只需维护一份：

@../ai-foundation-memory/series-overview.md

## 关键架构要点（开发时不得违背）

- **多单元组合（units+edges）**：combos.yaml = 多端治理真源；units key = 生成目录名，edges = 有序对 [consumer, provider]，provider 契约属主。桥只管 N≥2，单模板形态走能力层 generate_single（bridge-mcp-server）。
- **统一 Click CLI（cli.py）**：`generate <combo> <project>`（combo 子命令惰性构建）+ `check`。选项由各 unit 底座 params.json schema 数据驱动（不解析 copier.yml、不手抄参数）。
- **底座一律 clone/baked**：裸名 source 经 bases 注册表 clone 到 `~/.cache/fullstack-bridge/bases` + checkout combos.yaml version；可执行 `dist/bridge` 烘焙 params.json（frozen schema/help 零网络）。
- **派生只读**：暴露 derived:false 原生参数（含派生输入如 child_apps_raw）；derived:true 纯派生值（child_apps）由 copier 算、不暴露。

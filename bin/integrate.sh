#!/usr/bin/env bash
# fullstack-bridge 整合脚本：选定组合 + 参数 → 生成前后端一体大目录。
# 用法见 ../README.md；新增组合在下方「组合映射」加一行即可。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$BRIDGE_DIR/.venv/bin/python"
# 前端生成:copier(前端模板已迁移 copier;--trust 执行其 _tasks 安装,此处 -T 跳过、生成后统一装)

# ── 组合映射（新增组合在此加一行）────────────────────────
# 组合名 | 前端模板 | 后端模板(copier 目录) | 契约模板
declare -A FRONTEND_TMPL=(
  [python-react]="$BRIDGE_DIR/../vite-react-spa-template/template"
)
declare -A BACKEND_TMPL=(
  [python-react]="$BRIDGE_DIR/../python-fastapi-template/template"
)
declare -A CONTRACT_TMPL=(
  [python-react]="$BRIDGE_DIR/python-react.md.jinja"
)

usage() {
  cat <<EOF
用法: integrate.sh <组合> <project_name> [选项]

可用组合: ${!FRONTEND_TMPL[*]}

选项:
  --description <文本>       前端描述（必填）
  --api-base-url <url>       前端 API 基础地址，默认 /api
  --auth-mode <none|opaque>  后端认证模式，默认 opaque
  --with-db <true|false>     后端是否带数据库，默认 true
  --with-redis <true|false>  后端是否带 Redis，默认 true
  --with-child-app <true|false>  后端是否带子应用，默认 true
  --child-apps <names>       子应用名，逗号分隔，默认 backend
  -h, --help                 显示本帮助
EOF
}

# ── 默认参数 ──────────────────────────────────────────
PROJECT=""
COMBIN=""
DESCRIPTION=""
API_BASE_URL="/api"
AUTH_MODE="opaque"
WITH_DB="true"
WITH_REDIS="true"
WITH_CHILD_APP="true"
CHILD_APPS="backend"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --description)     DESCRIPTION="$2";    shift 2 ;;
    --api-base-url)    API_BASE_URL="$2";   shift 2 ;;
    --auth-mode)       AUTH_MODE="$2";      shift 2 ;;
    --with-db)         WITH_DB="$2";        shift 2 ;;
    --with-redis)      WITH_REDIS="$2";     shift 2 ;;
    --with-child-app)  WITH_CHILD_APP="$2"; shift 2 ;;
    --child-apps)      CHILD_APPS="$2";     shift 2 ;;
    -h|--help)         usage; exit 0 ;;
    *)
      if [[ -z "$COMBIN" ]]; then
        COMBIN="$1"
      elif [[ -z "$PROJECT" ]]; then
        PROJECT="$1"
      else
        echo "未知参数: $1" >&2; usage; exit 1
      fi
      shift ;;
  esac
done

# ── 校验 ──────────────────────────────────────────────
[[ -n "$COMBIN" && -n "$PROJECT" ]] || { usage; exit 1; }
# 项目名取目标目录名（basename），用于派生前后端应用名
PROJECT_NAME="$(basename "$PROJECT")"
if [[ -z "${FRONTEND_TMPL[$COMBIN]:-}" ]]; then
  echo "未知组合: $COMBIN（可用: ${!FRONTEND_TMPL[*]}）" >&2
  exit 1
fi
[[ -n "$DESCRIPTION" ]] || { echo "--description 必填（前端生成要求）" >&2; exit 1; }
[[ -x "$PYTHON" ]] || {
  echo "缺少渲染环境: $PYTHON（请先执行: uv venv .venv && uv pip install --python .venv/bin/python jinja2）" >&2
  exit 1
}

# 失败保留现场：不清理半成品目录，提示排查位置
trap 'echo "❌ 失败（退出码 $?）：产物保留在 $PROJECT/ 供排查" >&2' ERR

echo "══ fullstack-bridge 整合：$COMBIN → $PROJECT/ ══"

# ── ① 骨架 ───────────────────────────────────────────
echo ""
echo "[1/6] 创建目录骨架"
mkdir -p "$PROJECT/frontend" "$PROJECT/backend" "$PROJECT/docs"

# ── ② 前端 ───────────────────────────────────────────
echo ""
# 前端需执行 _tasks（含 auth_mode=none 时删 src/auth 的条件裁剪 + 自动 pnpm install），故不加 -T
echo "[2/6] 生成前端 → $PROJECT/frontend"
copier copy "${FRONTEND_TMPL[$COMBIN]}" "$PROJECT/frontend" \
  -d "project_name=${PROJECT_NAME}-frontend" \
  -d "project_description=$DESCRIPTION" \
  -d "project_title=$PROJECT_NAME" \
  -d "api_base_url=$API_BASE_URL" \
  -d "auth_mode=$AUTH_MODE" \
  -l --trust

# ── ③ 后端 ───────────────────────────────────────────
echo ""
# 后端需执行 _tasks（含 auth_mode=none 时删 auth 文件的条件裁剪 + uv sync 装依赖），故不加 -T
echo "[3/6] 生成后端 → $PROJECT/backend"
copier copy "${BACKEND_TMPL[$COMBIN]}" "$PROJECT/backend" \
  -d "project_name=${PROJECT_NAME}-backend" \
  -d "auth_mode=$AUTH_MODE" \
  -d "with_db=$WITH_DB" \
  -d "with_redis=$WITH_REDIS" \
  -d "with_child_app=$WITH_CHILD_APP" \
  -d "child_apps_raw=$CHILD_APPS" \
  --defaults --trust

# ── ④ 契约渲染 ───────────────────────────────────────
echo ""
echo "[4/6] 渲染契约 → $PROJECT/docs/CONTRACT.md"
"$PYTHON" "$SCRIPT_DIR/render.py" "${CONTRACT_TMPL[$COMBIN]}" \
  -o "$PROJECT/docs/CONTRACT.md" \
  -d "auth_mode=$AUTH_MODE" \
  -d "with_db=$WITH_DB" \
  -d "with_redis=$WITH_REDIS" \
  -d "with_child_app=$WITH_CHILD_APP"

# ── ⑤ 入口 README ────────────────────────────────────
echo ""
echo "[5/6] 生成入口 README → $PROJECT/README.md"
"$PYTHON" "$SCRIPT_DIR/render.py" "$SCRIPT_DIR/templates/project-README.md.jinja" \
  -o "$PROJECT/README.md" \
  -d "project_name=$PROJECT"

# ── ⑥ 完成 ───────────────────────────────────────────
echo ""
echo "[6/6] 完成"
echo ""
echo "✅ 项目已生成: $PROJECT/"
echo "  $PROJECT/frontend/        前端应用（名 ${PROJECT_NAME}-frontend）"
echo "  $PROJECT/backend/         后端服务（名 ${PROJECT_NAME}-backend）"
echo "  $PROJECT/docs/CONTRACT.md 前后端契约（改动接口前先读它）"
echo "  $PROJECT/README.md        入口说明"
echo ""
echo "依赖已由生成器自动安装（前端 pnpm install / 后端 uv sync）"

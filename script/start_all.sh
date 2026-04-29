#!/bin/bash
# script/start_all.sh
# 一键启动后端、Celery 和前端服务

PROJECT_ROOT="${COMIC_DRAMA_PROJECT_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
export COMIC_DRAMA_PROJECT_ROOT="$PROJECT_ROOT"

echo "=== 启动项目所有服务 ==="
/bin/bash "$PROJECT_ROOT/script/start_backend.sh"
/bin/bash "$PROJECT_ROOT/script/start_celery.sh"
/bin/bash "$PROJECT_ROOT/script/start_frontend.sh"
echo "=== 所有服务已在后台启动 ==="
echo "后端: uvicorn (8000)"
echo "Celery: ai, video"
echo "前端: vite (5173)"
echo "查看日志请至 $PROJECT_ROOT/logs 目录"

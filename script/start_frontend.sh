#!/bin/bash
# script/start_frontend.sh
# 启动前端 Vite 开发服务器并将日志重定向到 logs/frontend.log

PROJECT_ROOT="${COMIC_DRAMA_PROJECT_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PROJECT_ROOT/frontend"

echo "正在启动前端 Vite 服务..."
nohup npm run dev > "$PROJECT_ROOT/logs/frontend.log" 2>&1 &
echo "前端服务已启动。PID: $!"
echo "日志文件: $PROJECT_ROOT/logs/frontend.log"

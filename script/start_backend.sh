#!/bin/bash
# script/start_backend.sh
# 启动后端 FastAPI 服务并将日志重定向到 logs/backend.log

PROJECT_ROOT="/Users/macbook/Documents/trae_projects/comic-drama-platform"
cd "$PROJECT_ROOT/backend"

echo "正在启动后端服务 (FastAPI/Uvicorn)..."
nohup ./.venv/bin/python -m uvicorn app.main:app --port 8000 --reload > "$PROJECT_ROOT/logs/backend.log" 2>&1 &
echo "后端服务已启动。PID: $!"
echo "日志文件: $PROJECT_ROOT/logs/backend.log"

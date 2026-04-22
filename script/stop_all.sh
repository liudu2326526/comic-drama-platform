#!/bin/bash
# script/stop_all.sh
# 一键停止后端、Celery 和前端服务

echo "正在停止 Uvicorn (FastAPI)..."
pkill -f uvicorn
echo "正在停止 Celery..."
pkill -f celery
echo "正在停止 Vite (npm run dev)..."
pkill -f vite
echo "=== 所有相关服务已停止 ==="

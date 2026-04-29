#!/bin/bash
# script/start_celery.sh
# 启动 Celery Workers 并将日志重定向到 logs/celery.log

PROJECT_ROOT="${COMIC_DRAMA_PROJECT_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PROJECT_ROOT/backend"

echo "正在启动 Celery Workers (ai, video)..."
# 启动 AI 队列 (4 并发)
nohup ./.venv/bin/celery -A app.tasks.celery_app worker -Q ai -c 4 --loglevel=info > "$PROJECT_ROOT/logs/celery_ai.log" 2>&1 &
echo "Celery AI Worker 已启动。PID: $!"

# 启动 Video 队列 (2 并发)
nohup ./.venv/bin/celery -A app.tasks.celery_app worker -Q video -c 2 --loglevel=info > "$PROJECT_ROOT/logs/celery_video.log" 2>&1 &
echo "Celery Video Worker 已启动。PID: $!"

echo "日志文件: $PROJECT_ROOT/logs/celery_ai.log, $PROJECT_ROOT/logs/celery_video.log"

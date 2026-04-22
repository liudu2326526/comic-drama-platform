#!/usr/bin/env bash
# frontend/scripts/smoke_m2.sh —— M2 前端 ↔ 后端 parse + storyboards 冒烟
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BE=${BE:-http://127.0.0.1:8000}
FE=${FE:-http://127.0.0.1:5173}

export no_proxy="localhost,127.0.0.1"
export NO_PROXY="localhost,127.0.0.1"
FE_PID_FILE=${FE_PID_FILE:-/tmp/comic-drama-fe.pid}
FE_LOG_FILE=${FE_LOG_FILE:-/tmp/comic-drama-fe.log}

cleanup() {
  if [[ -f "$FE_PID_FILE" ]]; then
    FE_PID="$(cat "$FE_PID_FILE")"
    kill "$FE_PID" 2>/dev/null || true
    wait "$FE_PID" 2>/dev/null || true
    rm -f "$FE_PID_FILE"
  fi
}
trap cleanup EXIT

echo "[1/8] 后端健康检查"
curl -fsS --noproxy "*" "$BE/healthz" | jq '.data'

echo "[2/8] 前端 typecheck + build"
( cd "$REPO_ROOT/frontend" && npm run typecheck && npm run build )

echo "[3/8] 启动前端 dev server"
( cd "$REPO_ROOT/frontend" && exec npm run dev >"$FE_LOG_FILE" 2>&1 ) &
echo $! > "$FE_PID_FILE"

echo "Waiting for frontend on $FE..."
for i in {1..20}; do
  if curl -s --noproxy "*" "$FE" > /dev/null; then
    echo "Frontend is up!"
    break
  fi
  if [[ $i -eq 20 ]]; then
    echo "Frontend failed to start. Logs:"
    cat "$FE_LOG_FILE"
    exit 1
  fi
  sleep 1
done

STORY=$(python3 -c 'print("从前有座山,山上有座庙..." * 10)')

echo "[4/8] 创建项目"
PID=$(curl -fsS --noproxy "*" -X POST "$FE/api/v1/projects" \
  -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg name '前端 M2 冒烟' --arg story "$STORY" '{name:$name, story:$story}')" \
  | jq -r .data.id)
echo "created: $PID"

echo "[5/8] 触发 parse"
JOB_ID=$(curl -fsS --noproxy "*" -X POST "$FE/api/v1/projects/$PID/parse" | jq -r .data.job_id)
echo "parse job: $JOB_ID"

echo "[6/8] 轮询 job(EAGER 模式应已终态)"
for i in {1..20}; do
  STATUS=$(curl -fsS --noproxy "*" "$FE/api/v1/jobs/$JOB_ID" | jq -r .data.status)
  echo "  job status: $STATUS"
  if [[ "$STATUS" == "succeeded" ]]; then break; fi
  if [[ "$STATUS" == "failed" || "$STATUS" == "canceled" ]]; then
    curl -s --noproxy "*" "$FE/api/v1/jobs/$JOB_ID" | jq .
    exit 1
  fi
  sleep 1
done
[[ "$STATUS" == "succeeded" ]] || { echo "job did not reach succeeded in 20s"; exit 1; }

echo "[7/8] 校验分镜列表 + 阶段(DRAFT)"
N=$(curl -fsS --noproxy "*" "$FE/api/v1/projects/$PID/storyboards" | jq '.data | length')
echo "  storyboards count: $N"
[[ "$N" -ge 1 ]] || { echo "expected >=1 storyboard"; exit 1; }

STAGE=$(curl -fsS --noproxy "*" "$FE/api/v1/projects/$PID" | jq -r .data.stage_raw)
echo "  stage_raw (before confirm): $STAGE"
[[ "$STAGE" == "draft" ]] || { echo "expected draft, got $STAGE"; exit 1; }

echo "[8/8] 手动新增一个分镜"
NEW_SHOT_ID=$(curl -fsS --noproxy "*" -X POST "$FE/api/v1/projects/$PID/storyboards" \
  -H 'Content-Type: application/json' \
  -d '{"title":"手动新增分镜","description":"smoke test","idx":99}' \
  | jq -r .data.id)
echo "  new shot: $NEW_SHOT_ID"

echo "[9/8] 确认分镜 (推进到 storyboard_ready)"
curl -fsS --noproxy "*" -X POST "$FE/api/v1/projects/$PID/storyboards/confirm" | jq .
STAGE=$(curl -fsS --noproxy "*" "$FE/api/v1/projects/$PID" | jq -r .data.stage_raw)
echo "  stage_raw (after confirm): $STAGE"
[[ "$STAGE" == "storyboard_ready" ]] || { echo "expected storyboard_ready, got $STAGE"; exit 1; }

# 再做一轮 reorder 往返:反转
IDS=$(curl -fsS --noproxy "*" "$FE/api/v1/projects/$PID/storyboards" | jq -c '[.data[].id] | reverse')
curl -fsS --noproxy "*" -X POST "$FE/api/v1/projects/$PID/storyboards/reorder" \
  -H 'Content-Type: application/json' \
  -d "$(jq -nc --argjson ids "$IDS" '{ordered_ids: $ids}')" | jq '.data'

echo "[10/8] 清理"
curl -fsS --noproxy "*" -X DELETE "$FE/api/v1/projects/$PID" | jq .

echo "✅ frontend M2 smoke passed"

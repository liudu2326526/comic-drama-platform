#!/usr/bin/env bash
set -euo pipefail

API="${API:-http://127.0.0.1:8000/api/v1}"

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "缺少 $1" >&2; exit 2; }
}
require curl
require jq

echo "[1/7] 需要一个已到 scenes_locked 的项目"
PID="${PID:-}"
if [[ -z "$PID" ]]; then
  echo "请先准备一个已有 scenes_locked 状态的 PID（可来自前置 M3a smoke）"
  exit 2
fi

SHOT_ID="$(curl -s "$API/projects/$PID" | jq -r '.data.storyboards[0].id')"
echo "[2/7] 先获取 render draft"
DRAFT="$(curl -s -X POST "$API/projects/$PID/shots/$SHOT_ID/render-draft")"
PROMPT="$(echo "$DRAFT" | jq -r '.data.prompt')"
REFS="$(echo "$DRAFT" | jq -c '.data.references | map({id,kind,source_id,name,image_url})')"

echo "[3/7] 确认并发起单镜头 render"
ACK="$(curl -s -X POST "$API/projects/$PID/shots/$SHOT_ID/render" \
  -H 'Content-Type: application/json' \
  -d "{\"prompt\":$(jq -Rn --arg v "$PROMPT" '$v'),\"references\":$REFS}")"
JOB_ID="$(echo "$ACK" | jq -r '.data.job_id')"
echo "job=$JOB_ID"

echo "[4/7] 轮询 job 直到成功"
SUCCEEDED=0
for i in {1..90}; do
  ST="$(curl -s "$API/jobs/$JOB_ID" | jq -r '.data.status')"
  echo "  render job status: $ST"
  if [[ "$ST" == "succeeded" ]]; then
    SUCCEEDED=1
    break
  fi
  [[ "$ST" == "failed" ]] && { echo "render 失败"; exit 1; }
  sleep 2
done

if [[ "$SUCCEEDED" != "1" ]]; then
  echo "render job timed out before success" >&2
  curl -s "$API/jobs/$JOB_ID" | jq .
  exit 1
fi

echo "[5/7] 校验 render history"
ROWS="$(curl -s "$API/projects/$PID/shots/$SHOT_ID/renders")"
RID="$(echo "$ROWS" | jq -r '.data[0].id')"
[[ -n "$RID" && "$RID" != "null" ]] || { echo "未返回 render history"; exit 1; }

echo "[6/7] 选择当前版本"
curl -s -X POST "$API/projects/$PID/shots/$SHOT_ID/renders/$RID/select" | jq .

echo "[7/7] 锁定最终版并校验 stage"
curl -s -X POST "$API/projects/$PID/shots/$SHOT_ID/lock" | jq .
curl -s "$API/projects/$PID" | jq '.data | {stage_raw,generationQueue}'
echo "SMOKE M3b OK — project=$PID shot=$SHOT_ID render=$RID"

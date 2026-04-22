#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000/api/v1}"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing command: $1" >&2; exit 1; }
}

need curl
need jq

PROJECT_ID="${1:-}"
SHOT_ID="${2:-}"

if [[ -z "$PROJECT_ID" || -z "$SHOT_ID" ]]; then
  echo "usage: $0 <PROJECT_ID> <SHOT_ID>" >&2
  echo "project must already be at scenes_locked or rendering, and shot should be renderable" >&2
  exit 2
fi

echo "Build render draft..."
DRAFT="$(curl -fsS -X POST "$BASE_URL/projects/$PROJECT_ID/shots/$SHOT_ID/render-draft")"
PROMPT="$(echo "$DRAFT" | jq -r '.data.prompt')"
REFERENCES="$(echo "$DRAFT" | jq -c '.data.references | map({id,kind,source_id,name,image_url})')"

echo "Trigger single shot render..."
ACK="$(curl -fsS -X POST "$BASE_URL/projects/$PROJECT_ID/shots/$SHOT_ID/render" \
  -H 'Content-Type: application/json' \
  -d "{\"prompt\":$(jq -Rn --arg v "$PROMPT" '$v'),\"references\":$REFERENCES}")"
JOB_ID="$(echo "$ACK" | jq -r '.data.job_id')"
echo "job=$JOB_ID"

SUCCEEDED=0
for _ in $(seq 1 90); do
  JOB="$(curl -fsS "$BASE_URL/jobs/$JOB_ID")"
  STATUS="$(echo "$JOB" | jq -r '.data.status')"
  PROGRESS="$(echo "$JOB" | jq -r '.data.progress')"
  echo "status=$STATUS progress=$PROGRESS"
  if [[ "$STATUS" == "succeeded" ]]; then
    SUCCEEDED=1
    break
  fi
  if [[ "$STATUS" == "failed" || "$STATUS" == "canceled" ]]; then
    echo "$JOB" | jq .
    exit 1
  fi
  sleep 2
done

if [[ "$SUCCEEDED" != "1" ]]; then
  echo "render job timed out before success" >&2
  curl -fsS "$BASE_URL/jobs/$JOB_ID" | jq .
  exit 1
fi

JOB="$(curl -fsS "$BASE_URL/jobs/$JOB_ID")"
RENDER_ID="$(echo "$JOB" | jq -r '.data.result.render_id')"
if [[ -z "$RENDER_ID" || "$RENDER_ID" == "null" ]]; then
  echo "job succeeded but did not expose result.render_id" >&2
  echo "$JOB" | jq .
  exit 1
fi
echo "render=$RENDER_ID"

curl -fsS "$BASE_URL/projects/$PROJECT_ID/shots/$SHOT_ID/renders" | jq .
curl -fsS -X POST "$BASE_URL/projects/$PROJECT_ID/shots/$SHOT_ID/renders/$RENDER_ID/select" | jq .
curl -fsS -X POST "$BASE_URL/projects/$PROJECT_ID/shots/$SHOT_ID/lock" | jq .

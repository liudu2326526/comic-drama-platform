#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-http://127.0.0.1:8000}

echo "[1/5] healthz"
curl -fsS "$BASE/healthz" | jq .

echo "[2/5] create project"
PID=$(curl -fsS -X POST "$BASE/api/v1/projects" \
  -H 'Content-Type: application/json' \
  -d '{"name":"冒烟项目","story":"从前有座山","genre":"古风"}' | jq -r .data.id)
echo "created: $PID"

echo "[3/5] get project"
curl -fsS "$BASE/api/v1/projects/$PID" | jq '.data | {id, stage, stage_raw, name}'

echo "[4/5] rollback to same stage(应拒绝,预期 HTTP 403 + code=40301)"
RB_BODY=$(mktemp)
RB_CODE=$(curl -s -o "$RB_BODY" -w '%{http_code}' \
  -X POST "$BASE/api/v1/projects/$PID/rollback" \
  -H 'Content-Type: application/json' \
  -d '{"to_stage":"draft"}')
jq . "$RB_BODY"
if [[ "$RB_CODE" != "403" ]]; then
  echo "❌ expected HTTP 403, got $RB_CODE"; exit 1
fi
if [[ "$(jq -r .code "$RB_BODY")" != "40301" ]]; then
  echo "❌ expected body.code=40301"; exit 1
fi
rm -f "$RB_BODY"

echo "[5/5] delete"
curl -fsS -X DELETE "$BASE/api/v1/projects/$PID" | jq .

echo "✅ smoke passed"

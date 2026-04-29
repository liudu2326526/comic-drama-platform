#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-http://127.0.0.1:8000}

echo "--- M2 Smoke Test ---"

echo "[1/7] Create project"
PID=$(curl -fsS -X POST "$BASE/api/v1/projects" \
  -H 'Content-Type: application/json' \
  -d '{"name":"M2 冒烟项目","story":"在遥远的星系,有一个充满了魔法的星球..."}' | jq -r .data.id)
echo "Project created: $PID"

echo "[2/7] Trigger parse"
JID=$(curl -fsS -X POST "$BASE/api/v1/projects/$PID/parse" | jq -r .data.job_id)
echo "Parse job triggered: $JID"

echo "[3/7] Poll job status"
for i in {1..5}; do
  STATUS=$(curl -fsS "$BASE/api/v1/jobs/$JID" | jq -r .data.status)
  echo "Job status: $STATUS"
  if [[ "$STATUS" == "succeeded" ]]; then
    break
  fi
  sleep 1
done

if [[ "$STATUS" != "succeeded" ]]; then
  echo "❌ Job failed or still running: $STATUS"
  curl -fsS "$BASE/api/v1/jobs/$JID" | jq .
  exit 1
fi

echo "[4/7] Get project detail (verify parse)"
DETAIL=$(curl -fsS "$BASE/api/v1/projects/$PID")
echo "$DETAIL" | jq '.data | {summary, parsedStats, suggestedShots}'
SUMMARY=$(echo "$DETAIL" | jq -r .data.summary)
if [[ "$SUMMARY" == "" ]]; then
  echo "❌ Summary is empty"
  exit 1
fi

echo "[5/7] Verify storyboards count (after chained gen_storyboard)"
# 给链式任务一点时间
sleep 2
DETAIL=$(curl -fsS "$BASE/api/v1/projects/$PID")
COUNT=$(echo "$DETAIL" | jq '.data.storyboards | length')
echo "Current storyboards count: $COUNT"
if [[ "$COUNT" == "0" ]]; then
  echo "❌ Storyboards count is 0, gen_storyboard might have failed"
  exit 1
fi

echo "[6/7] Storyboard CRUD"
SIDS=$(echo "$DETAIL" | jq -r '.data.storyboards[0].id')
if [[ "$SIDS" != "null" ]]; then
  SID1=$SIDS
  echo "Updating storyboard $SID1"
  curl -fsS -X PATCH "$BASE/api/v1/projects/$PID/storyboards/$SID1" \
    -H 'Content-Type: application/json' \
    -d '{"title": "更新后的标题"}' | jq .
else
  echo "❌ No storyboard found to test CRUD"
  exit 1
fi

echo "[7/7] Delete project"
curl -fsS -X DELETE "$BASE/api/v1/projects/$PID" | jq .

echo "✅ M2 smoke passed"

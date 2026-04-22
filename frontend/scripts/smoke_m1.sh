#!/usr/bin/env bash
# frontend/scripts/smoke_m1.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BE=${BE:-http://127.0.0.1:8000}
FE=${FE:-http://127.0.0.1:5173}

# Bypass proxy for local requests
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

echo "[1/6] 后端健康检查"
curl -fsS --noproxy "*" "$BE/healthz" | jq '.data'

echo "[2/6] 前端 typecheck + build"
( cd "$REPO_ROOT/frontend" && npm run typecheck && npm run build )

echo "[3/6] 启动前端 dev server"
( cd "$REPO_ROOT/frontend" && exec npm run dev >"$FE_LOG_FILE" 2>&1 ) &
echo $! > "$FE_PID_FILE"

# Wait for frontend to be ready
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

echo "[4/6] 通过前端代理命中后端 /api/v1/projects"
# 创建
PID=$(curl -fsS --noproxy "*" -X POST "$FE/api/v1/projects" -H 'Content-Type: application/json' \
  -d '{"name":"前端冒烟","story":"从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙...从前有座山,山上有座庙..."}' | jq -r .data.id)
echo "created: $PID"

# 读
curl -fsS --noproxy "*" "$FE/api/v1/projects/$PID" | jq '.data | {id, stage, stage_raw, name}'

# 列
curl -fsS --noproxy "*" "$FE/api/v1/projects?page=1&page_size=50" | jq '.data.total'

echo "[5/6] rollback draft → draft(预期 403 / 40301)"
RB_BODY=$(mktemp)
RB_CODE=$(curl -s --noproxy "*" -o "$RB_BODY" -w '%{http_code}' \
  -X POST "$FE/api/v1/projects/$PID/rollback" -H 'Content-Type: application/json' \
  -d '{"to_stage":"draft"}')
jq . "$RB_BODY"
[[ "$RB_CODE" == "403" ]] || { echo "expected 403, got $RB_CODE"; exit 1; }
[[ "$(jq -r .code "$RB_BODY")" == "40301" ]] || { echo "expected body.code=40301"; exit 1; }
rm -f "$RB_BODY"

echo "[6/6] 清理"
curl -fsS --noproxy "*" -X DELETE "$FE/api/v1/projects/$PID" | jq .

echo "✅ frontend M1 smoke passed"

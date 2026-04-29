#!/usr/bin/env bash
# frontend/scripts/smoke_m3a.sh
# 前置:后端已在 127.0.0.1:8000 启动(AI_PROVIDER_MODE=mock + CELERY_TASK_ALWAYS_EAGER=true)
# 本脚本只打 API,不启动浏览器,验证前端依赖的后端 M3a 端点真实可用

set -euo pipefail

API="${API:-http://127.0.0.1:8000/api/v1}"
TS=$(date +%s)
NAME="m3a-fe-smoke-$TS"

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "缺少 $1,请先安装" >&2; exit 2; }
}
require curl
require jq

echo "[1/9] 创建项目 $NAME"
pid=$(curl -s -X POST "$API/projects" -H "Content-Type: application/json" \
  -d "$(jq -n --arg name "$NAME" '{name:$name, story:"古风权谋,皇权更迭,秦昭与江离,少年天子与摄政王的暗流。",ratio:"9:16"}')" \
  | jq -r '.data.id')
echo "  project id: $pid"

echo "[2/9] 触发 parse"
jid=$(curl -s -X POST "$API/projects/$pid/parse" | jq -r '.data.job_id')
echo "  job: $jid"

echo "[3/9] 等 parse 完成"
# parse_novel 任务体在 eager 模式下是同步的, 但由于 create_task, 我们仍需轮询
for i in {1..150}; do
  st=$(curl -s "$API/jobs/$jid" | jq -r '.data.status')
  echo "  parse job status: $st"
  [ "$st" = "succeeded" ] && break
  [ "$st" = "failed" ] && { echo "parse 失败"; exit 1; }
  sleep 2
done

# 等待 gen_storyboard
echo "等待 gen_storyboard 完成..."
for i in {1..150}; do
  gs_jid=$(curl -s "$API/projects/$pid/jobs" | jq -r '.data[] | select(.kind=="gen_storyboard") | .id' | head -n 1)
  if [ -n "$gs_jid" ]; then
    gs_st=$(curl -s "$API/jobs/$gs_jid" | jq -r '.data.status')
    echo "  gen_storyboard job ($gs_jid) status: $gs_st"
    [ "$gs_st" = "succeeded" ] && break
  fi
  sleep 2
done

# 强制 confirm 推进到 storyboard_ready
echo "推进到 storyboard_ready..."
for i in {1..5}; do
  resp=$(curl -s -X POST "$API/projects/$pid/storyboards/confirm")
  code=$(echo "$resp" | jq -r '.code')
  if [ "$code" = "0" ]; then
    echo "  confirm success"
    break
  fi
  echo "  confirm failed (code=$code), retrying..."
  sleep 2
done

stage_raw=$(curl -s "$API/projects/$pid" | jq -r '.data.stage_raw')
echo "  final stage_raw=$stage_raw"
[ "$stage_raw" = "storyboard_ready" ] || { echo "期望 storyboard_ready"; exit 1; }

echo "[4/9] 再次检查阶段"
# 确保阶段已正确推进
stage_raw=$(curl -s "$API/projects/$pid" | jq -r '.data.stage_raw')
echo "  current stage: $stage_raw"
[ "$stage_raw" = "storyboard_ready" ] || { echo "期望 storyboard_ready"; exit 1; }

echo "[5/9] 生成角色"
ack=$(curl -s -X POST "$API/projects/$pid/characters/generate" -H "Content-Type: application/json" -d '{}')
echo "  ack: $ack"
gjid=$(echo "$ack" | jq -r '.data.job_id')
echo "  generate job: $gjid"
for i in {1..150}; do
  st=$(curl -s "$API/jobs/$gjid" | jq -r '.data.status')
  echo "  generate job status: $st"
  [ "$st" = "succeeded" ] && break
  [ "$st" = "failed" ] && { echo "generate_characters 失败"; exit 1; }
  sleep 2
done
chars=$(curl -s "$API/projects/$pid" | jq '.data.characters | length')
[ "$chars" -gt 0 ] || { echo "角色未落库"; exit 1; }
echo "  characters=$chars"

echo "[6/9] 锁定主角(异步)"
cid=$(curl -s "$API/projects/$pid" | jq -r '.data.characters[0].id')
ack=$(curl -s -X POST "$API/projects/$pid/characters/$cid/lock" \
  -H "Content-Type: application/json" -d '{"as_protagonist": true}')
ljid=$(echo "$ack" | jq -r '.data.job_id')
[ "$(echo "$ack" | jq -r '.data.ack')" = "async" ] || { echo "expected async ack"; exit 1; }
for i in {1..150}; do
  st=$(curl -s "$API/jobs/$ljid" | jq -r '.data.status')
  echo "  lock job: $st"
  [ "$st" = "succeeded" ] && break
  [ "$st" = "failed" ] && { echo "lock failed"; exit 1; }
  sleep 2
done
stage_raw=$(curl -s "$API/projects/$pid" | jq -r '.data.stage_raw')
[ "$stage_raw" = "characters_locked" ] || { echo "期望 characters_locked 实际 $stage_raw"; exit 1; }
echo "  stage_raw=$stage_raw"

echo "[7/9] 生成场景 + 轮询"
sack=$(curl -s -X POST "$API/projects/$pid/scenes/generate" -H "Content-Type: application/json" -d '{}')
sjid=$(echo "$sack" | jq -r '.data.job_id')
echo "  scene job: $sjid"
for i in {1..150}; do
  st=$(curl -s "$API/jobs/$sjid" | jq -r '.data.status')
  echo "  scene job status: $st"
  [ "$st" = "succeeded" ] && break
  [ "$st" = "failed" ] && { echo "generate_scenes 失败"; exit 1; }
  sleep 2
done
scenes=$(curl -s "$API/projects/$pid" | jq '.data.scenes | length')
[ "$scenes" -gt 0 ] || { echo "场景未落库"; exit 1; }
echo "  scenes=$scenes"

echo "[8/9] 绑定每个镜头到第一个场景 + 只锁定被绑定场景"
first_scene=$(curl -s "$API/projects/$pid" | jq -r '.data.scenes[0].id')
for sid in $(curl -s "$API/projects/$pid" | jq -r '.data.storyboards[].id'); do
  curl -s -X POST "$API/projects/$pid/storyboards/$sid/bind_scene" \
    -H "Content-Type: application/json" -d "$(jq -n --arg sc "$first_scene" '{scene_id:$sc}')" >/dev/null
done
curl -s -X POST "$API/projects/$pid/scenes/$first_scene/lock" \
  -H "Content-Type: application/json" -d '{}' >/dev/null

echo "[9/9] 校验 stage=scenes_locked"
stage_raw=$(curl -s "$API/projects/$pid" | jq -r '.data.stage_raw')
[ "$stage_raw" = "scenes_locked" ] || { echo "期望 scenes_locked 实际 $stage_raw"; exit 1; }
echo "SMOKE M3A OK — project=$pid stage=$stage_raw"

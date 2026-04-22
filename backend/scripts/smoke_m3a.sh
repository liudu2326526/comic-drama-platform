#!/bin/bash
set -e

# Backend M3a 冒烟测试脚本
# 验证角色提取、资产生成、锁定、场景绑定等核心链路

BASE_URL=${BASE_URL:-"http://localhost:8000/api/v1"}
PROJECT_ID=$1

if [ -z "$PROJECT_ID" ]; then
    echo "Usage: $0 <PROJECT_ID>"
    exit 1
fi

echo "--- 1. 推进项目到 storyboard_ready ---"
# 假设项目已经有分镜, 这里强制推到 storyboard_ready (如果不在的话)
# 实际生产中是通过 gen_storyboard 任务完成自动推进的
curl -s -X PATCH "$BASE_URL/projects/$PROJECT_ID" \
     -H "Content-Type: application/json" \
     -d '{"stage": "storyboard_ready"}' | jq .

echo -e "\n--- 2. 生成角色 ---"
GEN_CHAR_RESP=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/characters/generate" \
     -H "Content-Type: application/json" \
     -d '{"extra_hints": []}')
echo $GEN_CHAR_RESP | jq .
JOB_ID=$(echo $GEN_CHAR_RESP | jq -r .data.job_id)

echo "等待角色生成任务 $JOB_ID 完成..."
while true; do
    STATUS=$(curl -s "$BASE_URL/jobs/$JOB_ID" | jq -r .data.status)
    echo "Job Status: $STATUS"
    if [ "$STATUS" == "succeeded" ]; then break; fi
    if [ "$STATUS" == "failed" ]; then echo "Job Failed!"; exit 1; fi
    sleep 2
done

echo -e "\n--- 3. 获取角色列表并锁定主角 ---"
CHARS_RESP=$(curl -s "$BASE_URL/projects/$PROJECT_ID/characters")
CHAR_ID=$(echo $CHARS_RESP | jq -r '.data[0].id')
echo "Locking Character $CHAR_ID as protagonist..."
curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/characters/$CHAR_ID/lock" \
     -H "Content-Type: application/json" \
     -d '{"as_protagonist": true}' | jq .

echo -e "\n--- 4. 生成场景 ---"
GEN_SCENE_RESP=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/scenes/generate" \
     -H "Content-Type: application/json" \
     -d '{}')
echo $GEN_SCENE_RESP | jq .
SCENE_JOB_ID=$(echo $GEN_SCENE_RESP | jq -r .data.job_id)

echo "等待场景生成任务 $SCENE_JOB_ID 完成..."
while true; do
    STATUS=$(curl -s "$BASE_URL/jobs/$SCENE_JOB_ID" | jq -r .data.status)
    echo "Job Status: $STATUS"
    if [ "$STATUS" == "succeeded" ]; then break; fi
    if [ "$STATUS" == "failed" ]; then echo "Job Failed!"; exit 1; fi
    sleep 2
done

echo -e "\n--- 5. 获取场景并锁定 ---"
SCENES_RESP=$(curl -s "$BASE_URL/projects/$PROJECT_ID/scenes")
SCENE_ID=$(echo $SCENES_RESP | jq -r '.data[0].id')
echo "Locking Scene $SCENE_ID..."
curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/scenes/$SCENE_ID/lock" | jq .

echo -e "\n--- 6. 绑定场景到分镜 ---"
SHOTS_RESP=$(curl -s "$BASE_URL/projects/$PROJECT_ID/storyboards")
SHOT_ID=$(echo $SHOTS_RESP | jq -r '.data[0].id')
echo "Binding Shot $SHOT_ID to Scene $SCENE_ID..."
curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/storyboards/$SHOT_ID/bind_scene?scene_id=$SCENE_ID" | jq .

echo -e "\n--- 7. 检查项目详情 ---"
curl -s "$BASE_URL/projects/$PROJECT_ID" | jq .

echo -e "\n--- M3a Smoke Test Passed! ---"

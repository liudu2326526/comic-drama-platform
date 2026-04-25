import asyncio
import importlib
import json
import re
from types import SimpleNamespace

import pytest

gen_storyboard = importlib.import_module("app.tasks.ai.gen_storyboard")
build_expand_segment_prompt = gen_storyboard.build_expand_segment_prompt
build_segment_plan_prompt = gen_storyboard.build_segment_plan_prompt
match_source_excerpt = gen_storyboard.match_source_excerpt
normalize_expanded_storyboard = gen_storyboard.normalize_expanded_storyboard


def test_match_source_excerpt_uses_query_window():
    story = (
        "第一段。宫墙外风平浪静，侍卫低声交谈。\n"
        "第二段。大雍天启二十三年秋末，雨夜皇城雷声滚过，朱雀门外积水翻涌，老宦官提灯急行。\n"
        "第三段。天色渐明，东宫偏殿里传来压低的争执声。"
    )

    excerpt, anchor = match_source_excerpt(
        story,
        {
            "source_query": "大雍 天启 秋末 雨夜 皇城 雷声 朱雀门 老宦官",
            "idx": 1,
        },
        window_chars=12,
    )

    assert "雨夜皇城雷声滚过" in excerpt
    assert "老宦官提灯急行" in excerpt
    assert anchor["match_score"] > 0
    assert anchor["start"] < anchor["end"]


def test_prompt_builders_define_segment_and_beat_contracts():
    story = "雨夜皇城，朱雀门外雷声滚过。"
    segment_prompt = build_segment_plan_prompt(story)
    expand_prompt = build_expand_segment_prompt(
        {"idx": 1, "title": "雨夜皇城", "description": "建立压抑氛围", "duration_sec": 8},
        "雨夜皇城，朱雀门外雷声滚过。",
    )

    assert "视频片段级分镜" in segment_prompt
    assert "source_query" in segment_prompt
    assert "5、8、10、12、15" in segment_prompt
    assert "2-4 个子镜头 beat" in expand_prompt
    assert "beats" in expand_prompt
    assert "source_excerpt" not in expand_prompt


def test_normalize_expanded_storyboard_preserves_v2_fields():
    segment = {
        "idx": 2,
        "title": "宫门惊雷",
        "description": "雨夜宫门外惊雷炸响。",
        "duration_sec": 8,
        "tags": ["雨夜"],
    }
    expanded = {
        "description": "雨夜宫门外惊雷炸响，宫灯剧烈摇晃。",
        "detail": "8秒，9:16竖屏。0-3s：远景俯拍宫门；3-8s：缓慢推进至老宦官。",
        "beats": [
            {"time": "0-3s", "shot_type": "远景", "camera_movement": "俯拍", "action": "雷光照亮宫门"},
            {"time": "3-8s", "shot_type": "中景", "camera_movement": "缓慢推进", "action": "老宦官提灯急行"},
        ],
        "tags": ["雨夜", "宫门"],
    }

    item = normalize_expanded_storyboard(segment, expanded, "原文片段", {"start": 4, "end": 20})

    assert item["idx"] == 2
    assert item["title"] == "宫门惊雷"
    assert item["source_excerpt"] == "原文片段"
    assert item["source_anchor"] == {"start": 4, "end": 20}
    assert len(item["beats"]) == 2
    assert item["tags"] == ["雨夜", "宫门"]


def test_normalize_expanded_storyboard_rejects_missing_beats():
    with pytest.raises(ValueError, match="beats"):
        normalize_expanded_storyboard(
            {"idx": 1, "title": "雨夜", "description": "雨夜", "duration_sec": 8},
            {"description": "雨夜", "detail": "8秒。"},
            "原文",
            {"start": 0, "end": 2},
        )


@pytest.mark.asyncio
async def test_expand_storyboard_segments_runs_ai_calls_concurrently():
    active = 0
    max_active = 0

    class FakeClient:
        async def chat_completions(self, model: str, messages: list[dict]):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            try:
                await asyncio.sleep(0.05)
                user_msg = messages[-1]["content"]
                idx = int(re.search(r'"idx":\s*(\d+)', user_msg).group(1))
                content = {
                    "idx": idx,
                    "title": f"分镜 {idx}",
                    "description": f"扩写 {idx}",
                    "detail": "8秒，9:16竖屏。0-4s：远景固定机位；4-8s：中景缓慢推进。",
                    "duration_sec": 8,
                    "tags": [f"分镜{idx}"],
                    "beats": [
                        {"time": "0-4s", "shot_type": "远景", "camera_movement": "固定机位", "action": "建立空间"},
                        {"time": "4-8s", "shot_type": "中景", "camera_movement": "缓慢推进", "action": "推进情绪"},
                    ],
                }
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(content, ensure_ascii=False)))]
                )
            finally:
                active -= 1

    segments = [
        {"idx": 1, "title": "一", "description": "一", "duration_sec": 8},
        {"idx": 2, "title": "二", "description": "二", "duration_sec": 8},
        {"idx": 3, "title": "三", "description": "三", "duration_sec": 8},
    ]
    source_pairs = [
        ("原文一", {"start": 0, "end": 3}),
        ("原文二", {"start": 3, "end": 6}),
        ("原文三", {"start": 6, "end": 9}),
    ]
    progress: list[int] = []

    results = await gen_storyboard._expand_storyboard_segments(
        FakeClient(),
        "test-model",
        segments,
        source_pairs,
        on_item_done=lambda done: progress.append(done),
    )

    assert max_active > 1
    assert [item["idx"] for item in results] == [1, 2, 3]
    assert progress == [1, 2, 3]

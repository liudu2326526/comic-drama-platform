import pytest

from app.tasks.ai.gen_storyboard import (
    build_expand_segment_prompt,
    build_segment_plan_prompt,
    match_source_excerpt,
    normalize_expanded_storyboard,
)


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

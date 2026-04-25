import json

import pytest

from app.infra.volcano_client import MockVolcanoClient


@pytest.mark.asyncio
async def test_mock_volcano_selects_shot_reference_ids() -> None:
    response = await MockVolcanoClient().chat_completions(
        "mock-chat",
        [
            {"role": "user", "content": "请先为当前镜头选择参考图。\n候选参考图：[]"},
        ],
    )

    payload = json.loads(response.choices[0].message.content)

    assert payload["reference_ids"] == []
    assert "selection_notes" in payload


@pytest.mark.asyncio
async def test_mock_volcano_generates_shot_draft_prompt() -> None:
    response = await MockVolcanoClient().chat_completions(
        "mock-chat",
        [
            {"role": "user", "content": "请基于当前镜头与已选参考图，生成一份可直接用于视频生成的草稿提示词。"},
        ],
    )

    payload = json.loads(response.choices[0].message.content)

    assert payload["prompt"]
    assert "optimizer_notes" in payload


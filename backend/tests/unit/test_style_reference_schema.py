from app.domain.schemas.project import ProjectDetail
from app.domain.schemas.style_reference import StyleReferenceState, prompt_text


def test_style_reference_state_defaults_to_empty():
    state = StyleReferenceState()

    assert state.imageUrl is None
    assert state.prompt is None
    assert state.status == "empty"
    assert state.error is None


def test_project_detail_includes_style_reference_states():
    detail = ProjectDetail(
        id="p1",
        name="雨夜",
        stage="角色设定中",
        stage_raw="storyboard_ready",
        genre=None,
        ratio="9:16",
        story="story",
    )

    assert detail.characterStyleReference.status == "empty"
    assert detail.sceneStyleReference.status == "empty"


def test_prompt_text_extracts_strings_and_profile_dicts():
    assert prompt_text("  宫廷冷雨  ") == "宫廷冷雨"
    assert prompt_text({"prompt": "无人皇城"}) == "无人皇城"
    assert prompt_text({"text": "ignored"}) is None

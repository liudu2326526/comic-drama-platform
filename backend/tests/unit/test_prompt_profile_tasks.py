from types import SimpleNamespace

from app.tasks.ai.gen_character_prompt_profile import build_character_prompt_profile_messages
from app.tasks.ai.gen_scene_prompt_profile import build_scene_prompt_profile_messages


def _project():
    return SimpleNamespace(
        name="雨夜",
        genre="古风权谋",
        ratio="9:16",
        story="宁王世子萧临渊雨夜入宫，奉密诏清除太子党羽。",
        summary="雨夜皇城权谋开局",
        overview="皇帝借萧临渊为刀，太子暗中反制。",
        setup_params=["冷雨", "宫廷", "权谋"],
    )


def _joined(messages: list[dict[str, str]]) -> str:
    return "\n".join(message["content"] for message in messages)


def test_character_prompt_profile_messages_include_project_context():
    text = _joined(build_character_prompt_profile_messages(_project()))

    assert "雨夜" in text
    assert "古风权谋" in text
    assert "宁王世子萧临渊雨夜入宫" in text
    assert "皇帝借萧临渊为刀" in text
    assert "冷雨" in text


def test_scene_prompt_profile_messages_include_project_context():
    text = _joined(build_scene_prompt_profile_messages(_project()))

    assert "雨夜" in text
    assert "古风权谋" in text
    assert "宁王世子萧临渊雨夜入宫" in text
    assert "皇帝借萧临渊为刀" in text
    assert "宫廷" in text

from datetime import UTC, datetime

from app.domain.models import Character, Scene, StoryboardShot
from app.domain.services.shot_draft_service import ShotDraftService


def test_select_references_prioritizes_scene_and_character_text_matches() -> None:
    service = ShotDraftService(session=None)  # type: ignore[arg-type]
    shot = StoryboardShot(
        id="shot-1",
        project_id="project-1",
        idx=7,
        title="帝王独坐，灯下待臣",
        description="太极殿后养心阁内，年过五旬的皇帝独坐灯下批阅奏章",
        detail="室内暖调烛火对比窗外冷调雨雾，皇帝眉眼带疲，双目仍锐利如鹰",
        tags=["皇帝", "养心阁"],
        status="pending",
    )
    scenes = [
        Scene(
            id="scene-rain-gate",
            project_id="project-1",
            name="雨夜朱雀门，死人生还",
            summary="萧临渊持密诏牌出现在朱雀门，震惊守门禁军",
            description="暴雨夜里的朱雀门宫门场景",
            reference_image_url="projects/p/scene/rain.png",
            updated_at=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
        ),
        Scene(
            id="scene-study",
            project_id="project-1",
            name="养心阁密议，君臣角力",
            summary="萧临渊入宫后到养心阁觐见皇帝",
            description="养心阁内皇帝独坐灯下批阅奏章，窗外雨气渗入殿内",
            reference_image_url="projects/p/scene/study.png",
            updated_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        ),
    ]
    characters = [
        Character(
            id="char-xiao",
            project_id="project-1",
            name="萧临渊",
            summary="宁王世子，雨夜入宫的黑氅青年",
            description="苍白年轻的俊脸，黑氅旧竹伞",
            reference_image_url="projects/p/character/xyl.png",
            created_at=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
        ),
        Character(
            id="char-emperor",
            project_id="project-1",
            name="萧承宗",
            summary="大雍皇帝，常服独坐灯下批阅奏章",
            description="年过五旬，眉眼带疲，双目锐利如鹰",
            reference_image_url="projects/p/character/emperor.png",
            created_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        ),
    ]

    references = service._select_references(shot, scenes, characters)

    scene_refs = [item for item in references if item["kind"] == "scene"]
    character_refs = [item for item in references if item["kind"] == "character"]

    assert scene_refs[0]["source_id"] == "scene-study"
    assert character_refs[0]["source_id"] == "char-emperor"

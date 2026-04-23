import pytest

from tests.integration.test_shot_render_api import seed_renderable_project

from app.domain.services.shot_video_service import ShotVideoService


@pytest.mark.asyncio
async def test_create_video_version_uses_raw_prompt_and_selected_params(db_session):
    project, shot = await seed_renderable_project(db_session)
    svc = ShotVideoService(db_session)

    video = await svc.create_video_version(
        project.id,
        shot.id,
        prompt="原样提示词",
        references=[{
            "id": "scene:1",
            "kind": "scene",
            "source_id": "scene01",
            "name": "东宫",
            "image_url": "https://example.com/scene.png",
        }],
        duration=5,
        resolution="720p",
        model_type="fast",
    )

    assert video.version_no == 1
    assert video.prompt_snapshot["prompt"] == "原样提示词"
    assert video.prompt_snapshot["references"][0]["image_url"] == "https://example.com/scene.png"
    assert video.params_snapshot["duration"] == 5
    assert video.params_snapshot["resolution"] == "720p"
    assert video.params_snapshot["model_type"] == "fast"


@pytest.mark.asyncio
async def test_create_video_version_omits_duration_when_not_selected(db_session):
    project, shot = await seed_renderable_project(db_session)
    svc = ShotVideoService(db_session)

    video = await svc.create_video_version(
        project.id,
        shot.id,
        prompt="原样提示词",
        references=[{
            "id": "scene:1",
            "kind": "scene",
            "source_id": "scene01",
            "name": "东宫",
            "image_url": "https://example.com/scene.png",
        }],
        duration=None,
        resolution="480p",
        model_type="fast",
    )

    assert "duration" not in video.params_snapshot
    assert video.params_snapshot["resolution"] == "480p"

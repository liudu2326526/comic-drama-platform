import pytest
from sqlalchemy import select

from tests.integration.test_shot_render_api import seed_renderable_project

from app.domain.models import Character, Job, ShotVideoRender, StoryboardShot
from app.domain.services.job_service import JobService
from app.domain.services.shot_video_service import ShotVideoService
from app.infra.db import get_session_factory
from app.tasks.video.render_shot_video import _render_shot_video_task


@pytest.mark.asyncio
async def test_render_shot_video_task_persists_video_and_last_frame(client, db_session, monkeypatch):
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
        }, {
            "id": "character:1",
            "kind": "character",
            "source_id": "char01",
            "name": "秦昭",
            "image_url": "https://example.com/char.png",
        }],
        duration=5,
        resolution="720p",
        model_type="fast",
    )
    assert video.prompt_snapshot["references"][1]["image_url"] == "https://example.com/char.png"
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot_video",
        target_type="shot",
        target_id=shot.id,
        payload={"shot_id": shot.id, "video_render_id": video.id},
    )
    await db_session.commit()

    class FakeClient:
        async def video_generations_create(self, **kwargs):
            return {"id": "cgt-123"}

        async def video_generations_get(self, task_id):
            return {
                "id": task_id,
                "status": "succeeded",
                "content": {
                    "video_url": "https://example.com/final.mp4",
                    "last_frame_url": "https://example.com/final.png",
                },
            }

    async def fake_persist_generated_asset(*, url, project_id, kind, ext):
        suffix = "mp4" if ext == "mp4" else "png"
        return f"projects/{project_id}/{kind}/20260423/out.{suffix}"

    monkeypatch.setattr("app.tasks.video.render_shot_video.get_volcano_client", lambda: FakeClient())
    monkeypatch.setattr("app.tasks.video.render_shot_video.persist_generated_asset", fake_persist_generated_asset)

    await _render_shot_video_task(shot.id, video.id, job.id)

    async with get_session_factory()() as session:
        saved = await session.get(ShotVideoRender, video.id)
        saved_shot = await session.get(StoryboardShot, shot.id)
        saved_job = await session.get(Job, job.id)
        assert saved.status == "succeeded"
        assert saved.video_url.endswith(".mp4")
        assert saved.last_frame_url.endswith(".png")
        assert saved_shot.current_video_render_id == video.id
        assert saved_job.status == "succeeded"


@pytest.mark.asyncio
async def test_render_shot_video_task_humanizes_input_image_privacy_filter_error(
    client, db_session, monkeypatch
):
    from app.infra.volcano_errors import VolcanoContentFilterError

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
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot_video",
        target_type="shot",
        target_id=shot.id,
        payload={"shot_id": shot.id, "video_render_id": video.id},
    )
    await db_session.commit()

    class FakeClient:
        async def video_generations_create(self, **kwargs):
            raise VolcanoContentFilterError("InputImageSensitiveContentDetected.PrivacyInformation")

    monkeypatch.setattr("app.tasks.video.render_shot_video.get_volcano_client", lambda: FakeClient())

    await _render_shot_video_task(shot.id, video.id, job.id)

    async with get_session_factory()() as session:
        saved = await session.get(ShotVideoRender, video.id)
        saved_shot = await session.get(StoryboardShot, shot.id)
        saved_job = await session.get(Job, job.id)
        assert saved.status == "failed"
        assert saved.error_code == "content_filter"
        assert saved.error_msg == "参考图被平台判定含隐私或敏感信息，请更换参考图后重试"
        assert saved_shot.current_video_render_id is None
        assert saved_job.status == "failed"
        assert saved_job.error_msg == "参考图被平台判定含隐私或敏感信息，请更换参考图后重试"


@pytest.mark.asyncio
async def test_render_shot_video_task_prefers_asset_uri_for_registered_character(
    client, db_session, monkeypatch
):
    project, shot = await seed_renderable_project(db_session)
    character = (
        await db_session.execute(
            select(Character).where(Character.project_id == project.id)
        )
    ).scalars().first()
    assert character is not None
    character.video_style_ref = {
        "asset_id": "asset-registered-char-001",
        "asset_status": "Active",
    }
    await db_session.commit()

    svc = ShotVideoService(db_session)
    video = await svc.create_video_version(
        project.id,
        shot.id,
        prompt="原样提示词",
        references=[
            {
                "id": "scene:1",
                "kind": "scene",
                "source_id": "scene01",
                "name": "东宫",
                "image_url": "https://example.com/scene.png",
            },
            {
                "id": f"character:{character.id}",
                "kind": "character",
                "source_id": character.id,
                "name": character.name,
                "image_url": "https://example.com/char.png",
            },
        ],
        duration=5,
        resolution="720p",
        model_type="fast",
    )
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot_video",
        target_type="shot",
        target_id=shot.id,
        payload={"shot_id": shot.id, "video_render_id": video.id},
    )
    await db_session.commit()

    captured: dict = {}

    class FakeClient:
        async def video_generations_create(self, **kwargs):
            captured["references"] = kwargs["references"]
            assert kwargs["references"] == [
                "https://example.com/scene.png",
                "asset://asset-registered-char-001",
            ]
            return {"id": "cgt-asset-1"}

        async def video_generations_get(self, task_id):
            return {
                "id": task_id,
                "status": "succeeded",
                "content": {
                    "video_url": "https://example.com/final.mp4",
                    "last_frame_url": "https://example.com/final.png",
                },
            }

    async def fake_persist_generated_asset(*, url, project_id, kind, ext):
        suffix = "mp4" if ext == "mp4" else "png"
        return f"projects/{project_id}/{kind}/20260423/out.{suffix}"

    monkeypatch.setattr("app.tasks.video.render_shot_video.get_volcano_client", lambda: FakeClient())
    monkeypatch.setattr("app.tasks.video.render_shot_video.persist_generated_asset", fake_persist_generated_asset)

    await _render_shot_video_task(shot.id, video.id, job.id)
    assert captured["references"] == [
        "https://example.com/scene.png",
        "asset://asset-registered-char-001",
    ]

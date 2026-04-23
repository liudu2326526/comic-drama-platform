import pytest

from tests.integration.test_shot_render_api import seed_renderable_project

from app.domain.models import Job, ShotVideoRender
from app.domain.services.job_service import JobService
from app.infra.ulid import new_id


@pytest.mark.asyncio
async def test_project_detail_exposes_current_video_render_id(client, db_session):
    project, shot = await seed_renderable_project(db_session)
    shot.current_video_render_id = "VID123"
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}")

    assert resp.status_code == 200
    rows = resp.json()["data"]["storyboards"]
    assert rows[0]["current_video_render_id"] == "VID123"


@pytest.mark.asyncio
async def test_post_video_returns_job_ack(client, db_session, monkeypatch, settings):
    project, shot = await seed_renderable_project(db_session)
    project.stage = "rendering"
    await db_session.commit()

    class FakeTask:
        id = "celery-video-1"

    monkeypatch.setattr("app.api.shots.render_shot_video_task.delay", lambda *args: FakeTask())
    settings.celery_task_always_eager = False

    resp = await client.post(
        f"/api/v1/projects/{project.id}/shots/{shot.id}/video",
        json={
            "prompt": "原样提示词",
            "references": [{
                "id": "scene:1",
                "kind": "scene",
                "source_id": "scene01",
                "name": "东宫",
                "image_url": "https://example.com/scene.png",
            }],
            "duration": 5,
            "resolution": "720p",
            "model_type": "fast",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["job_id"]


@pytest.mark.asyncio
async def test_project_detail_includes_video_generation_queue_fields(client, db_session):
    project, shot = await seed_renderable_project(db_session)
    video = ShotVideoRender(
        id=new_id(),
        shot_id=shot.id,
        version_no=1,
        status="succeeded",
        params_snapshot={"duration": 5, "resolution": "720p", "model_type": "fast"},
        video_url="projects/p/shot-video/v1.mp4",
        last_frame_url="projects/p/shot-video/v1.png",
    )
    db_session.add(video)
    await db_session.flush()
    shot.current_video_render_id = video.id
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot_video",
        target_type="shot",
        target_id=shot.id,
        payload={"shot_id": shot.id, "video_render_id": video.id},
    )
    job.status = "succeeded"
    job.result = {"shot_id": shot.id, "video_render_id": video.id, "video_url": video.video_url}
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}")
    storyboard = next(item for item in resp.json()["data"]["storyboards"] if item["id"] == shot.id)
    row = next(item for item in resp.json()["data"]["generationQueue"] if item["id"] == job.id)
    assert storyboard["current_video_render_id"] == video.id
    assert storyboard["current_video_url"].endswith(".mp4")
    assert row["video_render_id"] == video.id
    assert row["video_url"].endswith(".mp4")
    assert row["last_frame_url"].endswith(".png")
    assert row["params_snapshot"]["duration"] == 5

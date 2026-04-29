from sqlalchemy import select
import pytest

from app.domain.models import Project, ShotVideoRender, StoryboardShot


@pytest.mark.asyncio
async def test_video_submit_persists_generate_audio(client, db_session, monkeypatch, settings):
    class FakeTask:
        id = "task-audio"

    settings.celery_task_always_eager = False
    monkeypatch.setattr("app.api.shots.render_shot_video_task.delay", lambda *args: FakeTask())
    project = Project(name="p", story="现代末世故事" * 30, genre="现代末世", ratio="9:16", stage="scenes_locked")
    db_session.add(project)
    await db_session.flush()
    shot = StoryboardShot(project_id=project.id, idx=1, title="断电", description="城市断电", detail="天台")
    db_session.add(shot)
    await db_session.commit()
    await db_session.refresh(project)
    await db_session.refresh(shot)
    shot_id = shot.id

    resp = await client.post(
        f"/api/v1/projects/{project.id}/shots/{shot_id}/video",
        json={
            "prompt": "现代城市断电,风声和远处警报声",
            "references": [{"id": "manual:1", "kind": "manual", "name": "ref", "image_url": "https://static.example.com/a.png"}],
            "resolution": "480p",
            "model_type": "fast",
            "generate_audio": True,
        },
    )

    assert resp.status_code == 200
    await db_session.rollback()
    video = (
        await db_session.execute(select(ShotVideoRender).where(ShotVideoRender.shot_id == shot_id))
    ).scalar_one()
    assert video.params_snapshot["generate_audio"] is True

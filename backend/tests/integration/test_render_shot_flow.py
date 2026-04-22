import pytest

from app.domain.models import Job, ShotRender, StoryboardShot
from app.domain.schemas.shot_render import RenderSubmitRequest
from app.domain.services.job_service import JobService
from app.domain.services.shot_render_service import ShotRenderService
from app.tasks.ai.render_shot import _render_shot_task

from tests.integration.test_shot_render_api import seed_renderable_project


@pytest.mark.asyncio
async def test_render_shot_task_persists_image_and_updates_status(client, db_session, monkeypatch):
    project, shot = await seed_renderable_project(db_session)
    render = await ShotRenderService(db_session).create_render_version(
        project.id,
        shot.id,
        RenderSubmitRequest(
            prompt="图片1中的宫门，图片2中的主角，电影感低机位。",
            references=[
                {
                    "id": "scene-1",
                    "kind": "scene",
                    "source_id": "scene01",
                    "name": "长安殿",
                    "image_url": "https://static.example.com/scene.png",
                }
            ],
        ),
    )
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"render_id": render.id},
    )
    await db_session.commit()

    class FakeClient:
        async def image_generations(self, model, prompt, **kwargs):
            assert kwargs["size"] == "1024x1792"
            return {"data": [{"url": "https://volcano.example/tmp-shot.png"}]}

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        assert kind == "shot"
        assert url == "https://volcano.example/tmp-shot.png"
        return f"projects/{project_id}/shot/{shot.id}/v1.png"

    monkeypatch.setattr("app.tasks.ai.render_shot.get_volcano_client", lambda: FakeClient())
    monkeypatch.setattr("app.tasks.ai.render_shot.persist_generated_asset", fake_persist_generated_asset)

    await _render_shot_task(shot.id, render.id, job.id)

    # 使用新的 session 验证结果,避免缓存干扰
    from app.infra.db import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        saved_render = await session.get(ShotRender, render.id)
        saved_shot = await session.get(StoryboardShot, shot.id)
        saved_job = await session.get(Job, job.id)

        assert saved_render.status == "succeeded"
        assert saved_render.image_url.endswith("/v1.png")
        assert saved_shot.status == "succeeded"
        assert saved_shot.current_render_id == render.id
        assert saved_job.status == "succeeded"
    assert saved_job.progress == 100
    assert saved_job.result["render_id"] == render.id


@pytest.mark.asyncio
async def test_render_shot_task_records_volcano_error(client, db_session, monkeypatch):
    from app.infra.volcano_errors import VolcanoContentFilterError

    project, shot = await seed_renderable_project(db_session)
    render = await ShotRenderService(db_session).create_render_version(
        project.id,
        shot.id,
        RenderSubmitRequest(
            prompt="图片1中的宫门，图片2中的主角，电影感低机位。",
            references=[
                {
                    "id": "scene-1",
                    "kind": "scene",
                    "source_id": "scene01",
                    "name": "长安殿",
                    "image_url": "projects/p/scene/1.png",
                }
            ],
        ),
    )
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"render_id": render.id},
    )
    await db_session.commit()

    class FakeClient:
        async def image_generations(self, model, prompt, **kwargs):
            raise VolcanoContentFilterError("内容违规")

    monkeypatch.setattr("app.tasks.ai.render_shot.get_volcano_client", lambda: FakeClient())

    await _render_shot_task(shot.id, render.id, job.id)

    from app.infra.db import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        saved_render = await session.get(ShotRender, render.id)
        saved_shot = await session.get(StoryboardShot, shot.id)
        saved_job = await session.get(Job, job.id)
        assert saved_render.status == "failed"
        assert saved_render.error_code == "content_filter"
        assert saved_shot.status == "failed"
        assert saved_job.status == "failed"


@pytest.mark.asyncio
async def test_render_shot_task_is_idempotent_for_succeeded_render(client, db_session, monkeypatch):
    project, shot = await seed_renderable_project(db_session)
    render = await ShotRenderService(db_session).create_render_version(
        project.id,
        shot.id,
        RenderSubmitRequest(
            prompt="图片1中的宫门，图片2中的主角，电影感低机位。",
            references=[
                {
                    "id": "scene-1",
                    "kind": "scene",
                    "source_id": "scene01",
                    "name": "长安殿",
                    "image_url": "projects/p/scene/1.png",
                }
            ],
        ),
    )
    render.status = "succeeded"
    render.image_url = "projects/p/shot/s/v1.png"
    shot.status = "succeeded"
    shot.current_render_id = render.id
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"render_id": render.id},
    )
    await db_session.commit()

    class ShouldNotCallClient:
        async def image_generations(self, model, prompt, **kwargs):
            raise AssertionError("already succeeded render must not call provider again")

    monkeypatch.setattr("app.tasks.ai.render_shot.get_volcano_client", lambda: ShouldNotCallClient())

    await _render_shot_task(shot.id, render.id, job.id)

    from app.infra.db import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        saved_render = await session.get(ShotRender, render.id)
        saved_job = await session.get(Job, job.id)
        assert saved_render.status == "succeeded"
        assert saved_job.status == "succeeded"
        assert saved_job.result["render_id"] == render.id


@pytest.mark.asyncio
async def test_render_shot_task_is_idempotent_for_running_render(client, db_session, monkeypatch):
    project, shot = await seed_renderable_project(db_session)
    render = await ShotRenderService(db_session).create_render_version(
        project.id,
        shot.id,
        RenderSubmitRequest(
            prompt="图片1中的宫门，图片2中的主角，电影感低机位。",
            references=[
                {
                    "id": "scene-1",
                    "kind": "scene",
                    "source_id": "scene01",
                    "name": "长安殿",
                    "image_url": "projects/p/scene/1.png",
                }
            ],
        ),
    )
    render.status = "running"
    shot.status = "generating"
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"render_id": render.id},
    )
    await db_session.commit()

    class ShouldNotCallClient:
        async def image_generations(self, model, prompt, **kwargs):
            raise AssertionError("running render re-delivery must not call provider again")

    monkeypatch.setattr("app.tasks.ai.render_shot.get_volcano_client", lambda: ShouldNotCallClient())

    await _render_shot_task(shot.id, render.id, job.id)

    from app.infra.db import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        saved_render = await session.get(ShotRender, render.id)
        saved_job = await session.get(Job, job.id)
        assert saved_render.status == "running"
        assert saved_job.status == "running"

import pytest
from sqlalchemy import select
import importlib

from app.api.errors import ApiError
from app.domain.models import Character, Job, Project, Scene, ShotDraft, ShotRender, StoryboardShot
from app.domain.schemas.shot_render import RenderSubmitRequest
from app.domain.services.job_service import JobService
from app.domain.services.shot_render_service import ShotRenderService
from app.infra.ulid import new_id
from app.pipeline.states import ProjectStageRaw


gen_shot_draft_module = importlib.import_module("app.tasks.ai.gen_shot_draft")


async def seed_renderable_project(session):
    project = Project(
        id=new_id(),
        name="M3b project",
        story="story",
        stage=ProjectStageRaw.SCENES_LOCKED.value,
        genre="古风",
        ratio="9:16",
    )
    session.add(project)
    await session.flush()

    scene = Scene(
        id=new_id(),
        project_id=project.id,
        name="长安殿",
        theme="palace",
        summary="大殿",
        description="金色宫殿",
        reference_image_url="projects/p/scene/20260422/s.png",
    )
    character = Character(
        id=new_id(),
        project_id=project.id,
        name="秦昭",
        role_type="supporting",
        summary="少年天子",
        description="黑发金冠",
        reference_image_url="projects/p/character/20260422/c.png",
    )
    shot = StoryboardShot(
        id=new_id(),
        project_id=project.id,
        idx=1,
        title="登殿",
        description="主角走入大殿",
        detail="低机位，金色光线",
        duration_sec=3.0,
        tags=["角色:秦昭", "场景:长安殿"],
        status="pending",
    )
    session.add_all([scene, character, shot])
    await session.commit()
    return project, shot


@pytest.mark.asyncio
async def test_build_render_draft_returns_prompt_and_references(db_session):
    project, shot = await seed_renderable_project(db_session)
    svc = ShotRenderService(db_session)
    draft = await svc.build_render_draft(project.id, shot.id)

    assert draft["shot_id"] == shot.id
    assert "图片1" in draft["prompt"]
    assert len(draft["references"]) == 2
    assert any(item["kind"] == "scene" for item in draft["references"])
    assert all(item["image_url"] for item in draft["references"])


@pytest.mark.asyncio
async def test_create_render_version_from_confirmed_payload_increments_version(db_session):
    project, shot = await seed_renderable_project(db_session)
    svc = ShotRenderService(db_session)
    render1 = await svc.create_render_version(
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
    render1.status = "failed"
    shot.status = "failed"
    await db_session.flush()
    render2 = await svc.create_render_version(
        project.id,
        shot.id,
        RenderSubmitRequest(
            prompt="图片1中的宫门，重试一个更庄严的机位。",
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

    assert render1.version_no == 1
    assert render2.version_no == 2
    assert render2.prompt_snapshot["prompt"] == "图片1中的宫门，重试一个更庄严的机位。"
    assert render2.prompt_snapshot["references"][0]["source_id"] == "scene01"


@pytest.mark.asyncio
async def test_post_render_draft_returns_job_ack(client, db_session, monkeypatch):
    project, shot = await seed_renderable_project(db_session)
    project.stage = ProjectStageRaw.CHARACTERS_LOCKED.value
    await db_session.commit()

    class _Message:
        content = (
            '{"prompt":"用于视频生成的镜头草稿","reference_ids":[],"optimizer_notes":{"issues":["动作细节不足"]}}'
        )

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    class FakeClient:
        async def chat_completions(self, *args, **kwargs):
            return _Response()

    monkeypatch.setattr(gen_shot_draft_module, "get_volcano_client", lambda: FakeClient())

    resp = await client.post(f"/api/v1/projects/{project.id}/shots/{shot.id}/render-draft")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["job_id"]
    assert data["sub_job_ids"] == []

    job = await db_session.get(Job, data["job_id"])
    assert job is not None
    assert job.kind == "gen_shot_draft"
    assert job.status == "succeeded"


@pytest.mark.asyncio
async def test_get_render_draft_returns_null_when_absent(client, db_session):
    project, shot = await seed_renderable_project(db_session)
    project.stage = ProjectStageRaw.CHARACTERS_LOCKED.value
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}/shots/{shot.id}/render-draft")

    assert resp.status_code == 200
    assert resp.json()["data"] is None


@pytest.mark.asyncio
async def test_post_render_draft_in_eager_mode_persists_latest_draft(client, db_session, monkeypatch):
    project, shot = await seed_renderable_project(db_session)
    project.stage = ProjectStageRaw.CHARACTERS_LOCKED.value
    await db_session.commit()

    class _Message:
        content = (
            '{"prompt":"用于视频生成的镜头草稿","reference_ids":[],"optimizer_notes":{"principles":["Seedance 角色一致性"]}}'
        )

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    class FakeClient:
        async def chat_completions(self, *args, **kwargs):
            return _Response()

    monkeypatch.setattr(gen_shot_draft_module, "get_volcano_client", lambda: FakeClient())

    resp = await client.post(f"/api/v1/projects/{project.id}/shots/{shot.id}/render-draft")

    assert resp.status_code == 200
    rows = (
        await db_session.execute(
            select(ShotDraft).where(ShotDraft.shot_id == shot.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].prompt == "用于视频生成的镜头草稿"

    get_resp = await client.get(f"/api/v1/projects/{project.id}/shots/{shot.id}/render-draft")
    data = get_resp.json()["data"]
    assert data["shot_id"] == shot.id
    assert data["prompt"] == "用于视频生成的镜头草稿"
    assert data["references"]
    assert data["optimizer_snapshot"]["principles"] == ["Seedance 角色一致性"]


@pytest.mark.asyncio
async def test_get_render_draft_returns_latest_version_when_multiple_drafts_exist(client, db_session):
    project, shot = await seed_renderable_project(db_session)
    project.stage = ProjectStageRaw.CHARACTERS_LOCKED.value
    await db_session.flush()
    db_session.add_all(
        [
            ShotDraft(
                shot_id=shot.id,
                version_no=1,
                prompt="第一版镜头草稿",
                references_snapshot=[{"id": "scene:first", "name": "长安殿"}],
                optimizer_snapshot={"principles": ["v1"]},
                source_snapshot={"shot_id": shot.id},
            ),
            ShotDraft(
                shot_id=shot.id,
                version_no=2,
                prompt="第二版镜头草稿",
                references_snapshot=[{"id": "scene:latest", "name": "养心阁"}],
                optimizer_snapshot={"principles": ["v2"]},
                source_snapshot={"shot_id": shot.id},
            ),
        ]
    )
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}/shots/{shot.id}/render-draft")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["version_no"] == 2
    assert data["prompt"] == "第二版镜头草稿"
    assert data["references"][0]["id"] == "scene:latest"
    assert data["optimizer_snapshot"]["principles"] == ["v2"]


@pytest.mark.asyncio
async def test_post_render_draft_conflicts_when_existing_job_running(client, db_session):
    project, shot = await seed_renderable_project(db_session)
    project.stage = ProjectStageRaw.CHARACTERS_LOCKED.value
    db_session.add(
        Job(
            project_id=project.id,
            kind="gen_shot_draft",
            target_type="shot",
            target_id=shot.id,
            status="running",
            payload={"shot_id": shot.id},
        )
    )
    await db_session.commit()

    resp = await client.post(f"/api/v1/projects/{project.id}/shots/{shot.id}/render-draft")

    assert resp.status_code == 409
    assert resp.json()["code"] == 40901


@pytest.mark.asyncio
async def test_post_single_shot_render_returns_job_and_render(client, db_session, monkeypatch, settings):
    project, shot = await seed_renderable_project(db_session)
    project.stage = ProjectStageRaw.CHARACTERS_LOCKED.value
    await db_session.commit()
    original_eager = settings.celery_task_always_eager
    settings.celery_task_always_eager = False
    try:
        class FakeTask:
            id = "celery-render-1"

        monkeypatch.setattr("app.api.shots.render_shot_task.delay", lambda *args: FakeTask())

        resp = await client.post(
            f"/api/v1/projects/{project.id}/shots/{shot.id}/render",
            json={
                "prompt": "图片1中的宫门，图片2中的主角，电影感低机位。",
                "references": [
                    {
                        "id": "scene-1",
                        "kind": "scene",
                        "source_id": "scene01",
                        "name": "长安殿",
                        "image_url": "projects/p/scene/1.png",
                    }
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["job_id"]
        assert body["sub_job_ids"] == []

        job = await db_session.get(Job, body["job_id"])
        render = await db_session.get(ShotRender, job.payload["render_id"])
        assert render.status == "queued"
        assert render.version_no == 1
    finally:
        settings.celery_task_always_eager = original_eager


@pytest.mark.asyncio
async def test_post_single_shot_render_uses_eager_branch_without_delay(client, db_session, monkeypatch, settings):
    project, shot = await seed_renderable_project(db_session)
    settings.celery_task_always_eager = True

    async def fake_render_task(shot_id, render_id, job_id):
        job = await db_session.get(Job, job_id)
        render = await db_session.get(ShotRender, render_id)
        render.status = "succeeded"
        render.image_url = "projects/p/shot/s/v1.png"
        job.status = "succeeded"
        job.progress = 100
        job.result = {"shot_id": shot_id, "render_id": render_id, "image_url": render.image_url}
        await db_session.commit()

    def fail_delay(*args, **kwargs):
        raise AssertionError("eager mode should bypass Celery .delay()")

    monkeypatch.setattr("app.api.shots._render_shot_task", fake_render_task)
    monkeypatch.setattr("app.api.shots.render_shot_task.delay", fail_delay)

    resp = await client.post(
        f"/api/v1/projects/{project.id}/shots/{shot.id}/render",
        json={
            "prompt": "图片1中的宫门，图片2中的主角，电影感低机位。",
            "references": [
                {
                    "id": "scene-1",
                    "kind": "scene",
                    "source_id": "scene01",
                    "name": "长安殿",
                    "image_url": "projects/p/scene/1.png",
                }
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["sub_job_ids"] == []


@pytest.mark.asyncio
async def test_list_select_and_lock_render(client, db_session):
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
    await db_session.commit()

    list_resp = await client.get(f"/api/v1/projects/{project.id}/shots/{shot.id}/renders")
    assert list_resp.status_code == 200
    assert list_resp.json()["data"][0]["is_current"] is False

    select_resp = await client.post(
        f"/api/v1/projects/{project.id}/shots/{shot.id}/renders/{render.id}/select"
    )
    assert select_resp.status_code == 200

    project.stage = "rendering"
    await db_session.commit()
    lock_resp = await client.post(f"/api/v1/projects/{project.id}/shots/{shot.id}/lock")
    assert lock_resp.status_code == 200
    assert lock_resp.json()["data"]["status"] == "locked"


@pytest.mark.asyncio
async def test_first_render_request_advances_scenes_locked_to_rendering(db_session):
    from app.domain.models import Project
    from app.domain.schemas.shot_render import RenderSubmitRequest
    from app.domain.services.shot_render_service import ShotRenderService

    project, shot = await seed_renderable_project(db_session)
    project.stage = ProjectStageRaw.CHARACTERS_LOCKED.value
    await ShotRenderService(db_session).create_render_version(
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
    saved = await db_session.get(Project, project.id)
    assert saved.stage == "rendering"


@pytest.mark.asyncio
async def test_locking_all_succeeded_shots_advances_to_ready_for_export(db_session):
    from app.domain.models import Project
    from app.domain.schemas.shot_render import RenderSubmitRequest
    from app.domain.services.shot_render_service import ShotRenderService

    project, shot = await seed_renderable_project(db_session)
    project.stage = "rendering"
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
    await db_session.commit()

    await ShotRenderService(db_session).lock_shot(project.id, shot.id)
    saved = await db_session.get(Project, project.id)
    assert saved.stage == "ready_for_export"


@pytest.mark.asyncio
async def test_project_detail_includes_current_render_queue_item(client, db_session):
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
    job.status = "running"
    job.progress = 100
    job.result = {"shot_id": shot.id, "render_id": render.id, "image_url": render.image_url}
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["generationProgress"] == "1 / 1 已完成"
    assert data["generationQueue"][0]["id"] == job.id
    assert data["generationQueue"][0]["kind"] == "render_shot"
    assert data["generationQueue"][0]["progress"] == 100
    assert data["generationQueue"][0]["target_id"] == shot.id
    assert data["generationQueue"][0]["shot_id"] == shot.id
    assert data["generationQueue"][0]["render_id"] == render.id
    assert data["generationQueue"][0]["image_url"].endswith("/v1.png")
    assert data["generationQueue"][0]["error_code"] is None
    assert data["generationQueue"][0]["error_msg"] is None
    assert data["generationNotes"]["input"]


@pytest.mark.asyncio
async def test_project_jobs_list_exposes_target_and_payload_for_render_recovery(client, db_session):
    project, shot = await seed_renderable_project(db_session)
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"shot_id": shot.id, "render_id": "R1"},
    )
    job.status = "running"
    job.progress = 45
    job.done = 45
    job.total = 100
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}/jobs")
    assert resp.status_code == 200
    row = resp.json()["data"][0]
    assert row["id"] == job.id
    assert row["target_id"] == shot.id
    assert row["payload"]["shot_id"] == shot.id
    assert row["payload"]["render_id"] == "R1"
    assert row["error_msg"] is None


@pytest.mark.asyncio
async def test_build_render_draft_includes_candidates_without_locking(db_session):
    project, shot = await seed_renderable_project(db_session)
    extra_scene = Scene(
        id=new_id(),
        project_id=project.id,
        name="偏殿",
        reference_image_url="projects/p/scene/extra.png",
    )
    extra_char = Character(
        id=new_id(),
        project_id=project.id,
        name="额外角色",
        role_type="supporting",
        reference_image_url="projects/p/character/unlocked.png",
    )
    db_session.add_all([extra_scene, extra_char])
    await db_session.commit()

    svc = ShotRenderService(db_session)
    draft = await svc.build_render_draft(project.id, shot.id)
    assert {r["name"] for r in draft["references"] if r["kind"] == "character"} == {"秦昭", "额外角色"}
    assert {r["name"] for r in draft["references"] if r["kind"] == "scene"} == {"长安殿", "偏殿"}


@pytest.mark.asyncio
async def test_lock_shot_validates_render_status_and_ownership(db_session):
    project, shot = await seed_renderable_project(db_session)
    # 提前到允许锁定的阶段
    project.stage = "rendering"
    await db_session.commit()
    
    svc = ShotRenderService(db_session)

    # 1. 没有 current_render_id
    with pytest.raises(ValueError, match="镜头没有当前渲染版本"):
        await svc.lock_shot(project.id, shot.id)

    # 2. render 状态不是 succeeded
    render = ShotRender(
        id=new_id(),
        shot_id=shot.id,
        version_no=1,
        status="failed",
    )
    db_session.add(render)
    shot.current_render_id = render.id
    await db_session.commit()
    with pytest.raises(ValueError, match="只有 succeeded 的版本可锁定"):
        await svc.lock_shot(project.id, shot.id)

    # 3. render 不属于该 shot
    other_shot = StoryboardShot(id=new_id(), project_id=project.id, idx=2, title="Other")
    db_session.add(other_shot)
    await db_session.flush()
    
    other_render = ShotRender(id=new_id(), shot_id=other_shot.id, version_no=1, status="succeeded")
    db_session.add(other_render)
    shot.current_render_id = other_render.id
    await db_session.commit()
    with pytest.raises(ApiError) as exc:
        await svc.lock_shot(project.id, shot.id)
    assert exc.value.code == 40401


@pytest.mark.asyncio
async def test_aggregate_service_includes_recent_finished_jobs(client, db_session):
    from app.domain.services.aggregate_service import AggregateService
    project, shot = await seed_renderable_project(db_session)
    
    # 创建一个已完成但非 current 的渲染任务
    render = ShotRender(
        id=new_id(),
        shot_id=shot.id,
        version_no=1,
        status="succeeded",
        prompt_snapshot={"prompt": "历史快照", "references": []}
    )
    db_session.add(render)
    await db_session.flush()
    
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"render_id": render.id}
    )
    job.status = "succeeded"
    job.progress = 100
    job.result = {"render_id": render.id}
    await db_session.commit()
    
    # 此时 shot.current_render_id 仍为空
    detail = await AggregateService(db_session).get_project_detail(project.id)
    # generationQueue 应该包含这个已完成的 job
    assert any(j["id"] == job.id for j in detail.generationQueue)
    # generationNotes.input 应该反映这个 render 的快照
    assert "历史快照" in detail.generationNotes["input"]


@pytest.mark.asyncio
async def test_aggregate_service_tolerates_render_job_with_null_result(db_session):
    from app.domain.services.aggregate_service import AggregateService

    project, shot = await seed_renderable_project(db_session)
    render = ShotRender(
        id=new_id(),
        shot_id=shot.id,
        version_no=1,
        status="running",
        prompt_snapshot={"prompt": "排队中的镜头", "references": []},
    )
    db_session.add(render)
    await db_session.flush()

    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"render_id": render.id},
    )
    job.status = "running"
    job.progress = 5
    job.result = None
    await db_session.commit()

    detail = await AggregateService(db_session).get_project_detail(project.id)

    queue_row = next(item for item in detail.generationQueue if item["id"] == job.id)
    assert queue_row["render_id"] == render.id
    assert queue_row["shot_id"] == shot.id

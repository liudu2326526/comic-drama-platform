import pytest

from app.domain.models import Character, Job, Project, Scene, ShotRender, StoryboardShot
from app.domain.schemas.shot_render import RenderSubmitRequest
from app.domain.services.shot_render_service import ShotRenderService
from app.infra.ulid import new_id
from app.pipeline.states import ProjectStageRaw
from app.pipeline.transitions import InvalidTransition


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
        locked=True,
        reference_image_url="projects/p/scene/20260422/s.png",
    )
    character = Character(
        id=new_id(),
        project_id=project.id,
        name="秦昭",
        role_type="protagonist",
        is_protagonist=True,
        summary="少年天子",
        description="黑发金冠",
        locked=True,
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
    assert draft["references"]
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

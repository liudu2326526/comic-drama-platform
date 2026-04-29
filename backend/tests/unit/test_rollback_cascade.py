"""
这是跑在真实 MySQL 测试库上的"准单测"(需要 DB),因为 rollback_stage
里走的 UPDATE ... WHERE 必须让 DB 告诉我们 rowcount。
放在 unit/ 下是因为它只测 pipeline 这个子模块,不走 HTTP。
"""
import pytest
from sqlalchemy import select

from app.domain.models import Character, Project, Scene, StoryboardShot
from app.infra.ulid import new_id
from app.pipeline import ProjectStageRaw, rollback_stage
from app.pipeline.storyboard_states import StoryboardStatus


async def _seed(db_session, stage: str = "rendering") -> Project:
    p = Project(id=new_id(), name="回退", story="x", stage=stage, ratio="9:16")
    db_session.add(p)
    await db_session.flush()
    # 3 条 storyboards,1 条 locked status,1 条 character,1 条 scene
    for i in range(3):
        db_session.add(StoryboardShot(
            id=new_id(), project_id=p.id, idx=i, title=f"t{i}",
            status=StoryboardStatus.SUCCEEDED.value,
            scene_id=new_id(),              # 故意塞个假 scene_id
            current_render_id=new_id(),
        ))
    db_session.add(Character(
        id=new_id(), project_id=p.id, name="A", role_type="lead",
        is_protagonist=True, locked=True,
    ))
    db_session.add(Scene(
        id=new_id(), project_id=p.id, name="S1", locked=True,
    ))
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_rollback_clears_storyboard_bindings(db_session):
    p = await _seed(db_session)
    counts = await rollback_stage(db_session, p, ProjectStageRaw.STORYBOARD_READY)
    await db_session.flush()

    assert counts.shots_reset == 3
    assert counts.characters_unlocked == 0
    assert counts.scenes_unlocked == 0

    shots = (await db_session.execute(
        select(StoryboardShot).where(StoryboardShot.project_id == p.id)
    )).scalars().all()
    assert all(s.scene_id is None for s in shots)
    assert all(s.current_render_id is None for s in shots)
    assert all(s.status == "pending" for s in shots)

    chars = (await db_session.execute(
        select(Character).where(Character.project_id == p.id)
    )).scalars().all()
    assert all(c.locked for c in chars)

    scenes = (await db_session.execute(
        select(Scene).where(Scene.project_id == p.id)
    )).scalars().all()
    assert all(s.locked for s in scenes)


@pytest.mark.asyncio
async def test_rollback_to_same_stage_denied(db_session):
    from app.pipeline.transitions import InvalidTransition
    p = await _seed(db_session, stage="storyboard_ready")
    with pytest.raises(InvalidTransition):
        await rollback_stage(db_session, p, ProjectStageRaw.STORYBOARD_READY)


@pytest.mark.asyncio
async def test_rollback_forward_denied(db_session):
    from app.pipeline.transitions import InvalidTransition
    p = await _seed(db_session, stage="draft")
    with pytest.raises(InvalidTransition):
        await rollback_stage(db_session, p, ProjectStageRaw.RENDERING)

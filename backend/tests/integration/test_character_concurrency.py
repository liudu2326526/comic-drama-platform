import asyncio
import pytest
from sqlalchemy import select
from app.domain.models import Project, Character
from app.pipeline.states import ProjectStageRaw
from app.domain.services import CharacterService


@pytest.mark.asyncio
async def test_lock_protagonist_concurrency(db_session, project_factory, test_engine):
    # 强制设置全局 engine 供 get_session_factory 使用
    from app.infra import db as db_module
    from sqlalchemy.ext.asyncio import async_sessionmaker
    db_module._engine = test_engine
    db_module._session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    
    try:
        # 1. 准备数据: 一个项目, 两个角色
        project = await project_factory(stage=ProjectStageRaw.STORYBOARD_READY.value)
        
        char1 = Character(project_id=project.id, name="Char 1", role_type="supporting")
        char2 = Character(project_id=project.id, name="Char 2", role_type="supporting")
        db_session.add_all([char1, char2])
        await db_session.commit()
        await db_session.refresh(char1)
        await db_session.refresh(char2)

        # 2. 模拟并发锁定不同角色为主角
        async def task(cid, as_pro):
            from app.infra.db import get_session_factory
            session_factory = get_session_factory()
            async with session_factory() as s:
                p = await s.get(Project, project.id)
                c = await s.get(Character, cid)
                print(f"Task for {cid}: p={p}, c={c}")
                if not p or not c:
                    print(f"FAILED TO GET p or c: {p}, {c}")
                    return
                await CharacterService.lock(s, p, c, as_protagonist=as_pro)
                await s.commit()
                print(f"Task for {cid} committed")

        await asyncio.gather(
            task(char1.id, True),
            task(char2.id, True)
        )

        # 3. 验证结果: 只有一个主角
        # 使用全新的 session 进行验证, 避免隔离级别(REPEATABLE READ)导致的不可见
        from app.infra.db import get_session_factory
        session_factory = get_session_factory()
        async with session_factory() as s_verify:
            project_v = await s_verify.get(Project, project.id)
            stmt = select(Character).where(Character.project_id == project.id, Character.is_protagonist.is_(True))
            pros = (await s_verify.execute(stmt)).scalars().all()
            
            # 调试输出
            print(f"Project stage: {project_v.stage}")
            print(f"Protagonists count: {len(pros)}")
            for p in pros:
                print(f"Protagonist: {p.id} {p.name}")
            
            assert len(pros) == 1
            assert project_v.stage == ProjectStageRaw.CHARACTERS_LOCKED.value
    finally:
        db_module._engine = None
        db_module._session_factory = None

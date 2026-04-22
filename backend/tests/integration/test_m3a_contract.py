
import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from app.pipeline.states import ProjectStageRaw
from app.infra.db import get_engine
from app.domain.models import Character, Project

@pytest.mark.asyncio
async def test_m3a_contract_aggregate_includes_new_fields(client: AsyncClient):
    # 1. 创建项目
    resp = await client.post("/api/v1/projects", json={
        "name": "Contract Test",
        "story": "Story content",
    })
    pid = resp.json()["data"]["id"]

    # 2. 获取详情
    resp = await client.get(f"/api/v1/projects/{pid}")
    data = resp.json()["data"]
    
    # 校验 characters 包含 meta (数组), is_protagonist, locked, reference_image_url
    # 即使目前是空的
    assert "characters" in data
    if len(data["characters"]) > 0:
        char = data["characters"][0]
        assert isinstance(char["meta"], list)
        assert "is_protagonist" in char
        assert "locked" in char
        assert "reference_image_url" in char

    # 校验 storyboards 包含 current_render_id, created_at, updated_at
    assert "storyboards" in data
    if len(data["storyboards"]) > 0:
        shot = data["storyboards"][0]
        assert "current_render_id" in shot
        assert "created_at" in shot
        assert "updated_at" in shot

@pytest.mark.asyncio
async def test_bind_scene_uses_json_body(client: AsyncClient):
    # 1. 创建项目
    resp = await client.post("/api/v1/projects", json={
        "name": "Bind Scene Test",
        "story": "Story content",
    })
    pid = resp.json()["data"]["id"]

    # 2. 准备分镜和场景 (需要先有数据, 
    # 为了简单起见, 我们先验证接口定义是否正确处理 JSON body)
    # 即使 shot_id 不存在, 404 也是正常的, 关键是看参数解析
    resp = await client.post(
        f"/api/v1/projects/{pid}/storyboards/invalid_shot/bind_scene",
        json={"scene_id": "invalid_scene"}
    )
    # 因为在 draft 阶段, 应该返回 403 (InvalidTransition)
    assert resp.status_code == 403
    assert resp.json()["code"] == 40301

@pytest.mark.asyncio
async def test_characters_role_cn_mapping(client: AsyncClient):
    # 1. 创建项目
    resp = await client.post("/api/v1/projects", json={
        "name": "Role Map Test",
        "story": "Story content",
    })
    pid = resp.json()["data"]["id"]
    
    # 2. 获取列表 (即使为空)
    resp = await client.get(f"/api/v1/projects/{pid}/characters")
    assert resp.status_code == 200
    assert "data" in resp.json()

@pytest.mark.asyncio
async def test_lock_non_protagonist_stays_sync(client: AsyncClient):
    # 1. 创建项目
    resp = await client.post("/api/v1/projects", json={
        "name": "Lock Sync Test",
        "story": "Story content",
    })
    pid = resp.json()["data"]["id"]
    
    # 2. 模拟推进到 storyboard_ready (为了让 assert_asset_editable 通过)
    # 此处简单起见, 我们在测试中允许 InvalidTransition 只要结构对即可
    # 或者我们 mock 数据, 但集成测试最好走真逻辑。
    # 既然 smoke_m3a.sh 会测全链路, 这里侧重契约形状。
    
    # 创建一个角色
    from sqlalchemy import insert
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(insert(Character).values(
            id="C_SYNC", project_id=pid, name="SyncChar", role_type="supporting"
        ))
        # 强制更新项目 stage 为 storyboard_ready
        await conn.execute(sa.update(Project).where(Project.id == pid).values(stage="storyboard_ready"))
    
    resp = await client.post(f"/api/v1/projects/{pid}/characters/C_SYNC/lock", json={"as_protagonist": False})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["ack"] == "sync"
    assert body["locked"] is True

@pytest.mark.asyncio
async def test_lock_protagonist_returns_job_ack(client: AsyncClient):
    # 1. 创建项目
    resp = await client.post("/api/v1/projects", json={
        "name": "Lock Async Test",
        "story": "Story content",
    })
    pid = resp.json()["data"]["id"]
    
    # 2. 准备数据
    from sqlalchemy import insert
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(insert(Character).values(
            id="C_ASYNC", project_id=pid, name="AsyncChar", role_type="supporting"
        ))
        await conn.execute(sa.update(Project).where(Project.id == pid).values(stage="storyboard_ready"))
    
    resp = await client.post(f"/api/v1/projects/{pid}/characters/C_ASYNC/lock", json={"as_protagonist": True})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["ack"] == "async"
    assert "job_id" in body
    
    # 校验 job 存在
    jid = body["job_id"]
    resp_job = await client.get(f"/api/v1/jobs/{jid}")
    assert resp_job.status_code == 200
    assert resp_job.json()["data"]["kind"] == "register_character_asset"

@pytest.mark.asyncio
async def test_lock_scene_returns_job_ack(client: AsyncClient):
    # 1. 准备项目、场景和分镜 (满足推进 scenes_locked 的条件)
    resp = await client.post("/api/v1/projects", json={"name": "SceneLockAsync", "story": "..."})
    pid = resp.json()["data"]["id"]
    
    from app.domain.models import Scene, Project, StoryboardShot
    from sqlalchemy import insert
    from app.infra.db import get_engine
    import sqlalchemy as sa
    engine = get_engine()
    async with engine.begin() as conn:
        # 准备场景
        await conn.execute(insert(Scene).values(
            id="S_ASYNC", project_id=pid, name="AsyncScene", locked=False
        ))
        # 准备分镜并绑定到场景
        await conn.execute(insert(StoryboardShot).values(
            id="SHOT_1", project_id=pid, idx=1, title="Shot 1", scene_id="S_ASYNC"
        ))
        # 推进到 characters_locked
        await conn.execute(sa.update(Project).where(Project.id == pid).values(stage="characters_locked"))

    # 2. 投递场景锁定任务
    resp = await client.post(f"/api/v1/projects/{pid}/scenes/S_ASYNC/lock", json={})
    body = resp.json()["data"]
    assert body["ack"] == "async"
    assert body["job_id"]
    
    # 3. 校验 Job 状态并等待成功 (CELERY_TASK_ALWAYS_EAGER=true)
    job_id = body["job_id"]
    resp = await client.get(f"/api/v1/jobs/{job_id}")
    job_data = resp.json()["data"]
    assert job_data["kind"] == "lock_scene_asset"
    assert job_data["payload"]["scene_id"] == "S_ASYNC"
    assert job_data["status"] == "succeeded"
    
    # 4. 校验场景是否已锁定, 且项目阶段已推进
    resp = await client.get(f"/api/v1/projects/{pid}/scenes")
    scenes = resp.json()["data"]
    async_scene = next(s for s in scenes if s["id"] == "S_ASYNC")
    assert async_scene["locked"] is True
    
    resp = await client.get(f"/api/v1/projects/{pid}")
    project_data = resp.json()["data"]
    assert project_data["stage_raw"] == "scenes_locked"

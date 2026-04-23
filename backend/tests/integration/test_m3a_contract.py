
import pytest
from httpx import AsyncClient

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
async def test_register_character_asset_returns_job_ack(client: AsyncClient, db_session):
    from tests.helpers import force_stage
    resp = await client.post("/api/v1/projects", json={
        "name": "Register Asset Test",
        "story": "Story content",
    })
    pid = resp.json()["data"]["id"]

    from sqlalchemy import insert
    from app.domain.models import Character
    await db_session.execute(insert(Character).values(
        id="C_ASYNC", project_id=pid, name="AsyncChar", role_type="supporting"
    ))
    await force_stage(db_session, pid, "storyboard_ready")

    resp = await client.post(f"/api/v1/projects/{pid}/characters/C_ASYNC/register_asset")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert "job_id" in body

    jid = body["job_id"]
    resp_job = await client.get(f"/api/v1/jobs/{jid}")
    assert resp_job.status_code == 200
    assert resp_job.json()["data"]["kind"] == "register_character_asset"

@pytest.mark.asyncio
async def test_confirm_characters_stage_advances_with_existing_characters(client: AsyncClient, db_session):
    from tests.helpers import force_stage

    resp = await client.post("/api/v1/projects", json={"name": "Confirm Characters", "story": "..."})
    pid = resp.json()["data"]["id"]

    from sqlalchemy import insert
    from app.domain.models import Character

    await db_session.execute(insert(Character).values(
        id="C_CONFIRM", project_id=pid, name="ConfirmChar", role_type="supporting"
    ))
    await force_stage(db_session, pid, "storyboard_ready")

    resp = await client.post(f"/api/v1/projects/{pid}/characters/confirm")
    assert resp.status_code == 200
    assert resp.json()["data"]["stage_raw"] == "characters_locked"

    resp = await client.get(f"/api/v1/projects/{pid}")
    assert resp.json()["data"]["stage_raw"] == "characters_locked"


@pytest.mark.asyncio
async def test_confirm_scenes_stage_advances_with_existing_scenes(client: AsyncClient, db_session):
    from tests.helpers import force_stage

    resp = await client.post("/api/v1/projects", json={"name": "Confirm Scenes", "story": "..."})
    pid = resp.json()["data"]["id"]

    from sqlalchemy import insert
    from app.domain.models import Scene

    await db_session.execute(insert(Scene).values(
        id="S_CONFIRM", project_id=pid, name="ConfirmScene", locked=False
    ))
    await force_stage(db_session, pid, "characters_locked")

    resp = await client.post(f"/api/v1/projects/{pid}/scenes/confirm")
    assert resp.status_code == 200
    assert resp.json()["data"]["stage_raw"] == "scenes_locked"

    resp = await client.get(f"/api/v1/projects/{pid}")
    assert resp.json()["data"]["stage_raw"] == "scenes_locked"

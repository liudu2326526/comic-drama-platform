import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_storyboard_edit_window_guard(client: AsyncClient, db_session):
    from tests.helpers import insert_storyboards, force_stage
    # 1. 创建项目
    resp = await client.post("/api/v1/projects", json={
        "name": "权限测试项目",
        "story": "故事内容...",
    })
    project_id = resp.json()["data"]["id"]

    # 2. 直接插入分镜
    shots = await insert_storyboards(db_session, project_id, count=1)
    shot_id = shots[0].id
    
    # 3. 在 storyboard_ready 阶段尝试编辑 (应允许)
    await force_stage(db_session, project_id, "storyboard_ready")
    resp = await client.patch(f"/api/v1/projects/{project_id}/storyboards/{shot_id}", json={
        "title": "新标题"
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "新标题"

    # 4. 在 characters_locked 阶段尝试编辑 (应禁止)
    await force_stage(db_session, project_id, "characters_locked")
    resp = await client.patch(f"/api/v1/projects/{project_id}/storyboards/{shot_id}", json={
        "title": "又改标题"
    })
    assert resp.status_code == 403
    assert resp.json()["code"] == 40301


@pytest.mark.asyncio
async def test_storyboard_reorder(client: AsyncClient, db_session):
    from tests.helpers import insert_storyboards
    # 1. 创建项目
    resp = await client.post("/api/v1/projects", json={
        "name": "重排测试项目",
        "story": "故事内容...",
    })
    project_id = resp.json()["data"]["id"]
    
    # 2. 直接插入 2 条分镜
    shots = await insert_storyboards(db_session, project_id, count=2)
    original_ids = [s.id for s in shots]
    reversed_ids = list(reversed(original_ids))
    
    # 3. 触发重排
    resp = await client.post(f"/api/v1/projects/{project_id}/storyboards/reorder", json={
        "ordered_ids": reversed_ids
    })
    assert resp.status_code == 200
    
    # 4. 验证顺序
    resp = await client.get(f"/api/v1/projects/{project_id}")
    new_storyboards = resp.json()["data"]["storyboards"]
    new_ids = [s["id"] for s in new_storyboards]
    assert new_ids == reversed_ids

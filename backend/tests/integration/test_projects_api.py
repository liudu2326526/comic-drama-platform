import pytest


@pytest.mark.asyncio
async def test_create_and_get_project(client):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "测试项目", "story": "从前有座山"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    pid = body["data"]["id"]
    assert len(pid) == 26
    assert body["data"]["stage"] == "draft"

    resp = await client.get(f"/api/v1/projects/{pid}")
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["name"] == "测试项目"
    assert body["data"]["stage"] == "草稿中"
    assert body["data"]["stage_raw"] == "draft"


@pytest.mark.asyncio
async def test_list_projects(client):
    await client.post("/api/v1/projects", json={"name": "A", "story": "a"})
    await client.post("/api/v1/projects", json={"name": "B", "story": "b"})
    resp = await client.get("/api/v1/projects?page=1&page_size=10")
    body = resp.json()
    # 依赖 client fixture 的 TRUNCATE 隔离,精确断言
    assert body["data"]["total"] == 2
    names = sorted(item["name"] for item in body["data"]["items"])
    assert names == ["A", "B"]
    assert all("stage_raw" in item for item in body["data"]["items"])


@pytest.mark.asyncio
async def test_update_project(client):
    r = await client.post("/api/v1/projects", json={"name": "原名", "story": "x"})
    pid = r.json()["data"]["id"]
    r = await client.patch(f"/api/v1/projects/{pid}", json={"name": "新名"})
    assert r.json()["data"]["name"] == "新名"


@pytest.mark.asyncio
async def test_delete_project(client):
    r = await client.post("/api/v1/projects", json={"name": "待删", "story": "x"})
    pid = r.json()["data"]["id"]
    r = await client.delete(f"/api/v1/projects/{pid}")
    assert r.json()["data"]["deleted"] is True
    r = await client.get(f"/api/v1/projects/{pid}")
    assert r.json()["code"] == 40401


@pytest.mark.asyncio
async def test_project_delete_cascade(client, db_session):
    from app.domain.models import Job, StoryboardShot
    from sqlalchemy import select
    from tests.helpers import insert_storyboards, insert_job

    # 1. 创建项目
    resp = await client.post("/api/v1/projects", json={
        "name": "级联删除测试",
        "story": "故事内容..."
    })
    project_id = resp.json()["data"]["id"]

    # 2. 插入 Job 和 Storyboard (直接使用 helper, 不走 /parse)
    await insert_job(db_session, project_id, kind="parse_novel")
    await insert_storyboards(db_session, project_id, count=2)
    
    # 验证数据已存在
    jobs = (await db_session.scalars(select(Job).where(Job.project_id == project_id))).all()
    assert len(jobs) > 0
    shots = (await db_session.scalars(select(StoryboardShot).where(StoryboardShot.project_id == project_id))).all()
    assert len(shots) == 2
    
    # 3. 删除项目
    await client.delete(f"/api/v1/projects/{project_id}")
    
    # 4. 验证级联删除
    # 注意: 级联删除是 DB 层面的, db_session 需要刷新或开启新事务
    await db_session.commit() # 确保删除已提交
    
    jobs_after = (await db_session.scalars(select(Job).where(Job.project_id == project_id))).all()
    assert len(jobs_after) == 0
    
    shots_after = (await db_session.scalars(select(StoryboardShot).where(StoryboardShot.project_id == project_id))).all()
    assert len(shots_after) == 0


@pytest.mark.asyncio
async def test_get_project_404(client):
    r = await client.get("/api/v1/projects/01H0000000000000000000NOPE")
    assert r.status_code == 404
    assert r.json()["code"] == 40401


@pytest.mark.asyncio
async def test_create_project_validation(client):
    r = await client.post("/api/v1/projects", json={"name": ""})  # 缺 story
    assert r.status_code == 422
    assert r.json()["code"] == 40001


@pytest.mark.asyncio
async def test_patch_explicit_null_rejected(client):
    r = await client.post("/api/v1/projects", json={"name": "n", "story": "s"})
    pid = r.json()["data"]["id"]
    r = await client.patch(f"/api/v1/projects/{pid}", json={"name": None})
    assert r.status_code == 422
    assert r.json()["code"] == 40001


@pytest.mark.asyncio
async def test_patch_empty_payload_noop(client):
    r = await client.post("/api/v1/projects", json={"name": "原名", "story": "s"})
    pid = r.json()["data"]["id"]
    r = await client.patch(f"/api/v1/projects/{pid}", json={})
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "原名"


@pytest.mark.asyncio
async def test_create_blank_name_rejected(client):
    r = await client.post("/api/v1/projects", json={"name": "   ", "story": "s"})
    assert r.status_code == 422
    assert r.json()["code"] == 40001


@pytest.mark.asyncio
async def test_create_setup_params_dict_rejected(client):
    r = await client.post("/api/v1/projects", json={
        "name": "n", "story": "s", "setup_params": {"era": "古风"},
    })
    assert r.status_code == 422
    assert r.json()["code"] == 40001

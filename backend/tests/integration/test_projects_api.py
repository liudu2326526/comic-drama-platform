import pytest


@pytest.mark.asyncio
async def test_create_and_get_project(client):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "测试项目", "story": "从前有座山", "genre": "古风"},
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
async def test_get_project_404(client):
    r = await client.get("/api/v1/projects/01H0000000000000000000NOPE")
    assert r.status_code == 404
    assert r.json()["code"] == 40401


@pytest.mark.asyncio
async def test_create_project_validation(client):
    r = await client.post("/api/v1/projects", json={"name": ""})  # 缺 story
    assert r.status_code == 422
    assert r.json()["code"] == 40001

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.pipeline import ProjectStageRaw

@pytest.mark.asyncio
async def test_full_parse_flow_eager(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    # 1. 强制启用 Celery Eager 模式
    from app.tasks.celery_app import celery_app
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    
    # 2. 创建项目
    resp = await client.post("/api/v1/projects", json={
        "name": "测试项目",
        "story": "很久很久以前,有一个勇敢的小骑士...",
        "genre": "奇幻",
        "ratio": "16:9"
    })
    assert resp.status_code == 200
    project_id = resp.json()["data"]["id"]

    # 3. 触发解析
    resp = await client.post(f"/api/v1/projects/{project_id}/parse")
    assert resp.status_code == 200
    job_id = resp.json()["data"]["job_id"]

    # 轮询直到成功 (ALWAYS_EAGER 在 pytest 下是异步的)
    import asyncio
    for _ in range(20):
        r = await client.get(f"/api/v1/jobs/{job_id}")
        if r.json()["data"]["status"] == "succeeded":
            break
        await asyncio.sleep(0.5)

    # 4. 验证 Job 状态 (因为是 ALWAYS_EAGER,解析任务应该已经同步完成)
    resp = await client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200
    job_data = resp.json()["data"]
    assert job_data["status"] == "succeeded"
    assert job_data["progress"] == 100

    # 5. 验证项目详情 (已被 parse_novel 更新)
    resp = await client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 200
    project_data = resp.json()["data"]
    assert project_data["summary"] != ""
    assert len(project_data["parsedStats"]) > 0
    assert project_data["suggestedShots"] == "建议镜头数 12"

    # 6. 验证分镜已生成且 Stage 已推进 (在 ALWAYS_EAGER 模式下, /parse 已经链式完成了 gen_storyboard)
    resp = await client.get(f"/api/v1/projects/{project_id}")
    project_data = resp.json()["data"]
    assert project_data["stage_raw"] == ProjectStageRaw.STORYBOARD_READY.value
    assert len(project_data["storyboards"]) == 10
    assert project_data["generationProgress"] == "0 / 10 已完成"

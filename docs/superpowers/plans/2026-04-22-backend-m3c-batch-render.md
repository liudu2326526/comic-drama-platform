# Backend M3c: 批量渲染父子 Job 聚合 + 幂等复用 + 恢复机制 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 M3b 单镜头渲染链路之上，交付 M3c 的 `render_batch`：支持一次性为全部或指定镜头创建父 job、分发多个 `render_shot` 子 job、聚合整体进度、在 60 秒窗口内复用相同批量请求，并在 worker 中断后基于 `parent_id + payload + provider_task_id` 恢复批量任务。

**Architecture:** 保持仓库既有分层：HTTP 只创建/复用批量 job 并返回 `GenerateJobAck`；镜头选择、版本创建、父子 job 建模放在 `ShotRenderService` 与 `JobService`；批量分发与恢复放在 `tasks/ai/render_shot.py`，provider 回查能力补到 `infra/volcano_client.py`。M3c 需要把“批量渲染输入”定义清楚：单镜头 M3b 仍走 `render-draft -> 用户确认 -> render`；批量渲染则在服务层为每个目标镜头即时冻结一份 `prompt_snapshot`，来源分两种：已有成功版本的镜头复用最近一次成功 render 的 `prompt_snapshot`，从未成功渲染过的镜头则复用 `build_render_draft()` 的选图与 prompt 逻辑生成一份 `source="batch_auto"` 的快照后直接入库。这样前端的“批量继续生成”不会依赖未持久化的草稿，也不会让实现者去猜输入来源。项目聚合与 jobs API 补齐 `parent_id`、批量失败摘要和恢复相关字段，前端才能把批量进度、部分失败和恢复提示做出来。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / Alembic / Celery / Redis / MySQL 8 / pytest-asyncio / httpx / respx。所有命令从 `backend/` 运行并使用 `./.venv/bin/<tool>`。

---

## References

- Backend spec: `docs/superpowers/specs/2026-04-20-backend-mvp-design.md` §5.1-§5.4, §6.3.6, §7.2-§7.4, §8.1, §11, §15 M3c
- Existing M3b plan: `docs/superpowers/plans/2026-04-22-backend-m3b-render-shot.md`
- Current implementation baseline:
  - `backend/app/api/shots.py`
  - `backend/app/domain/schemas/shot_render.py`
  - `backend/app/domain/services/shot_render_service.py`
  - `backend/app/domain/services/job_service.py`
  - `backend/app/tasks/ai/render_shot.py`
  - `backend/app/domain/models/job.py`
  - `backend/app/domain/services/aggregate_service.py`
  - `backend/app/api/projects.py`

## Scope

**Includes:**

- `POST /api/v1/projects/{project_id}/shots/render`
- `render_batch` 父 job 与 `render_shot` 子 job 的 `parent_id` 关系
- 60 秒窗口内完全相同批量请求的幂等复用
- 批量完成后对父 job 写入失败镜头摘要与 `sub_job_ids`
- worker 启动恢复时对 `render_batch` 和 `render_shot` 做差异化恢复
- `GET /projects/{id}/jobs` 与 `GET /projects/{id}` 聚合补齐批量任务所需字段
- `scripts/smoke_m3c.sh`

**Excludes:**

- M4 导出、`export_shot_snapshots`、FFmpeg 合成
- 重新设计单镜头 `render-draft` 契约
- 前端实现；本计划只交付后端 contract 与恢复能力

## Current Baseline Notes

- `Job.parent_id` 和 `kind="render_batch"` 已经在模型与数据库枚举里存在，但业务代码尚未消费。
- 当前 `ShotRenderService.create_render_version()` 只服务单镜头确认生成，不具备“批量选择镜头 + 复用/跳过已成功版本”的编排能力。
- 当前 `render_shot_task` 会把单镜头 job 更新为 `succeeded/failed`，但不会回写父 job `done/total/result`。
- 当前 `GET /projects/{id}/jobs` 没有 `parent_id`，前端无法把父批量 job 与子镜头 job 关联起来。
- 当前聚合层 `generationQueue` 对 `render_shot` 做了补强，但对 `render_batch` 仍然只是普通 job 行，没有失败镜头摘要和子任务计数。
- 当前代码没有持久化“待确认 draft”，所以 M3c 不能假设批量渲染能读取某个现成的 confirmed draft 记录；计划必须显式定义批量输入如何冻结到 `shot_renders.prompt_snapshot`。

## File Structure

**Create:**

```text
backend/tests/unit/test_render_batch_recovery.py
backend/tests/integration/test_render_batch_api.py
backend/tests/integration/test_render_batch_flow.py
backend/scripts/smoke_m3c.sh
```

**Modify:**

```text
backend/app/api/shots.py
backend/app/api/projects.py
backend/app/domain/schemas/shot_render.py
backend/app/domain/services/shot_render_service.py
backend/app/domain/services/job_service.py
backend/app/domain/services/aggregate_service.py
backend/app/pipeline/transitions.py
backend/app/tasks/ai/render_shot.py
backend/app/infra/volcano_client.py
backend/app/tasks/ai/__init__.py
backend/app/domain/schemas/__init__.py
backend/app/domain/services/__init__.py
backend/README.md
```

## Task 1: 批量请求 Schema 与幂等 Job 边界

**Files:**
- Modify: `backend/app/domain/schemas/shot_render.py`
- Modify: `backend/app/domain/services/job_service.py`
- Test: `backend/tests/integration/test_render_batch_api.py`

- [ ] **Step 1: 先写批量请求与幂等复用的 failing 测试**

在 `backend/tests/integration/test_render_batch_api.py` 新增：

```python
@pytest.mark.asyncio
async def test_render_batch_reuses_same_running_parent_job_within_60_seconds(client, db_session):
    project, shots = await seed_render_batch_project(db_session, shot_count=2)

    resp1 = await client.post(
        f"/api/v1/projects/{project.id}/shots/render",
        json={"shot_ids": [shots[0].id, shots[1].id], "force_regenerate": False},
    )
    resp2 = await client.post(
        f"/api/v1/projects/{project.id}/shots/render",
        json={"shot_ids": [shots[1].id, shots[0].id], "force_regenerate": False},
    )

    ack1 = resp1.json()["data"]
    ack2 = resp2.json()["data"]
    assert ack1["job_id"] == ack2["job_id"]
    assert ack1["sub_job_ids"] == ack2["sub_job_ids"]
```

- [ ] **Step 2: 运行测试确认缺少批量 schema 与复用逻辑**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_render_batch_api.py::test_render_batch_reuses_same_running_parent_job_within_60_seconds -v
```

Expected: FAIL，因为 `/shots/render` 尚未实现。

- [ ] **Step 3: 在 schema 中补齐批量请求对象**

更新 `backend/app/domain/schemas/shot_render.py`：

```python
class RenderBatchRequest(BaseModel):
    shot_ids: list[str] | None = None
    force_regenerate: bool = False


class RenderBatchResult(BaseModel):
    pending_shot_ids: list[str]
    failed_shot_ids: list[str]
    succeeded_shot_ids: list[str]
```

- [ ] **Step 4: 在 JobService 中实现批量 job 幂等辅助**

更新 `backend/app/domain/services/job_service.py`：

```python
import hashlib
import time
from sqlalchemy import select

class JobService:
    def build_render_batch_key(
        self,
        *,
        project_id: str,
        shot_ids: list[str],
        force_regenerate: bool,
        minute_bucket: int | None = None,
    ) -> str:
        bucket = minute_bucket or int(time.time() / 60)
        payload = f"{project_id}|{','.join(sorted(shot_ids))}|{int(force_regenerate)}|{bucket}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    async def find_reusable_render_batch(self, project_id: str, key: str) -> Job | None:
        stmt = (
            select(Job)
            .where(
                Job.project_id == project_id,
                Job.kind == "render_batch",
                Job.status.in_(("queued", "running")),
                Job.payload["idempotency_key"].as_string() == key,
            )
            .order_by(Job.created_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().first()
```

- [ ] **Step 5: 运行测试确认 schema / service 通过导入**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_render_batch_api.py -k reusable -v
```

Expected: 仍 FAIL，但失败点前移到缺少 endpoint/service 编排，而不是缺少 schema。

- [ ] **Step 6: Commit**

```bash
git add app/domain/schemas/shot_render.py app/domain/services/job_service.py tests/integration/test_render_batch_api.py
git commit -m "feat(backend): add m3c render batch schema and idempotency helpers"
```

## Task 2: `ShotRenderService` 批量选镜头与父子 Job 创建

**Files:**
- Modify: `backend/app/domain/services/shot_render_service.py`
- Modify: `backend/app/api/shots.py`
- Test: `backend/tests/integration/test_render_batch_api.py`

- [ ] **Step 1: 写 endpoint 级 failing 测试**

在 `backend/tests/integration/test_render_batch_api.py` 追加：

```python
@pytest.mark.asyncio
async def test_post_render_batch_returns_parent_and_child_jobs(client, db_session, monkeypatch):
    project, shots = await seed_render_batch_project(db_session, shot_count=3)

    async def fake_dispatch_render_batch(parent_job_id: str) -> None:
        return None

    monkeypatch.setattr("app.api.shots.dispatch_render_batch", fake_dispatch_render_batch)

    resp = await client.post(
        f"/api/v1/projects/{project.id}/shots/render",
        json={"shot_ids": None, "force_regenerate": False},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["job_id"]
    assert len(data["sub_job_ids"]) == 3
```

- [ ] **Step 2: 运行测试确认后端缺少新端点**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_render_batch_api.py::test_post_render_batch_returns_parent_and_child_jobs -v
```

Expected: FAIL with `404`。

- [ ] **Step 3: 在服务层实现批量镜头选择与 render version 创建**

在 `backend/app/domain/services/shot_render_service.py` 增加：

```python
async def create_batch_render_jobs(
    self,
    project_id: str,
    *,
    shot_ids: list[str] | None,
    force_regenerate: bool,
) -> tuple[Job, list[Job]]:
    project = await self._get_project(project_id)
    if project.stage not in RENDERABLE_STAGES:
        raise InvalidTransition(project.stage, "render_batch", "只有 scenes_locked/rendering 阶段允许批量渲染")

    selected = await self._list_batch_target_shots(project_id, shot_ids=shot_ids, force_regenerate=force_regenerate)
    if not selected:
        raise ValueError("没有可发起批量渲染的镜头")

    job_svc = JobService(self.session)
    idem_key = job_svc.build_render_batch_key(
        project_id=project_id,
        shot_ids=[shot.id for shot in selected],
        force_regenerate=force_regenerate,
    )
    reusable = await job_svc.find_reusable_render_batch(project_id, idem_key)
    if reusable is not None:
        sub_jobs = await job_svc.list_child_jobs(reusable.id)
        return reusable, sub_jobs

    parent = await job_svc.create_job(
        project_id=project_id,
        kind="render_batch",
        target_type="project",
        target_id=project_id,
        payload={"shot_ids": [shot.id for shot in selected], "force_regenerate": force_regenerate, "idempotency_key": idem_key},
    )
    parent.total = len(selected)

    sub_jobs: list[Job] = []
    for shot in selected:
        render = await self._create_render_version_for_batch(project, shot, force_regenerate=force_regenerate)
        job = await job_svc.create_job(
            project_id=project_id,
            kind="render_shot",
            target_type="shot",
            target_id=shot.id,
            payload={"render_id": render.id, "shot_id": shot.id},
            parent_id=parent.id,
        )
        sub_jobs.append(job)

    await self.session.flush()
    return parent, sub_jobs
```

并在同一个 task 中补齐 `_create_render_version_for_batch()` 的来源规则，避免批量输入悬空：

```python
async def _create_render_version_for_batch(
    self,
    project: Project,
    shot: StoryboardShot,
    *,
    force_regenerate: bool,
) -> ShotRender:
    latest_success = await self._get_latest_succeeded_render(shot.id)
    if latest_success is not None and not force_regenerate:
        snapshot = latest_success.prompt_snapshot or {}
    else:
        draft = await self.build_render_draft(project.id, shot.id)
        snapshot = {
            "source": "batch_auto",
            "prompt": draft["prompt"],
            "references": draft["references"],
            "shot": {
                "id": shot.id,
                "idx": shot.idx,
                "title": shot.title,
                "description": shot.description,
                "detail": shot.detail,
                "tags": shot.tags or [],
            },
        }
    return await self._insert_render_version_from_snapshot(project, shot, snapshot)
```

- [ ] **Step 4: 扩展 JobService 支持 `parent_id` 和列子任务**

更新 `backend/app/domain/services/job_service.py` 的 `create_job()`：

```python
async def create_job(
    self,
    project_id: str,
    kind: str,
    target_type: str | None = None,
    target_id: str | None = None,
    payload: dict | None = None,
    parent_id: str | None = None,
) -> Job:
    job = Job(
        id=new_id(),
        project_id=project_id,
        parent_id=parent_id,
        kind=kind,
        target_type=target_type,
        target_id=target_id,
        status="queued",
        progress=0,
        done=0,
        payload=payload,
    )
```

并新增：

```python
async def list_child_jobs(self, parent_id: str) -> list[Job]:
    stmt = select(Job).where(Job.parent_id == parent_id).order_by(Job.created_at)
    return (await self.session.execute(stmt)).scalars().all()
```

- [ ] **Step 5: 添加 API 端点**

在 `backend/app/api/shots.py` 增加：

```python
@router.post("/render")
async def render_batch(project_id: str, payload: RenderBatchRequest, db: AsyncSession = Depends(get_db)):
    svc = ShotRenderService(db)
    parent, sub_jobs = await svc.create_batch_render_jobs(
        project_id,
        shot_ids=payload.shot_ids,
        force_regenerate=payload.force_regenerate,
    )
    parent_id = parent.id
    sub_job_ids = [job.id for job in sub_jobs]
    await db.commit()
    try:
        await dispatch_render_batch(parent_id)
    except Exception as exc:
        await mark_render_batch_dispatch_failed(db, parent_id, sub_job_ids, str(exc))
        raise
    return ok(GenerateJobAck(job_id=parent_id, sub_job_ids=sub_job_ids).model_dump())
```

- [ ] **Step 6: 运行测试验证 parent/sub-job 契约**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_render_batch_api.py -v
```

Expected: PASS `render_batch` 契约用例；后续恢复与聚合用例仍未实现。

- [ ] **Step 7: Commit**

```bash
git add app/api/shots.py app/domain/services/shot_render_service.py app/domain/services/job_service.py tests/integration/test_render_batch_api.py
git commit -m "feat(backend): add m3c render batch endpoint and parent jobs"
```

## Task 3: 子任务聚合、部分失败结果与父 Job 完成判定

**Files:**
- Modify: `backend/app/tasks/ai/render_shot.py`
- Modify: `backend/app/pipeline/transitions.py`
- Test: `backend/tests/integration/test_render_batch_flow.py`

- [ ] **Step 1: 先写批量完成后的聚合 failing 测试**

在 `backend/tests/integration/test_render_batch_flow.py` 新增：

```python
@pytest.mark.asyncio
async def test_child_render_updates_parent_done_and_failed_summary(db_session, monkeypatch):
    project, shots = await seed_render_batch_project(db_session, shot_count=2)
    parent, sub_jobs = await ShotRenderService(db_session).create_batch_render_jobs(
        project.id, shot_ids=None, force_regenerate=False
    )
    await db_session.commit()

    class FakeClient:
        async def image_generations(self, **kwargs):
            if "镜头标题:镜头 2" in kwargs["prompt"]:
                raise VolcanoContentFilterError("blocked")
            return {"data": [{"url": "https://example.com/fake.png"}]}

    async def fake_persist_generated_asset(**kwargs):
        return "projects/p/shot/generated.png"

    monkeypatch.setattr("app.tasks.ai.render_shot.get_volcano_client", lambda: FakeClient())
    monkeypatch.setattr("app.tasks.ai.render_shot.persist_generated_asset", fake_persist_generated_asset)
```

断言：

```python
    await _render_shot_task(shots[0].id, sub_jobs[0].payload["render_id"], sub_jobs[0].id)
    await _render_shot_task(shots[1].id, sub_jobs[1].payload["render_id"], sub_jobs[1].id)

    parent = await db_session.get(Job, parent.id)
    assert parent.done == 2
    assert parent.total == 2
    assert parent.status == "failed"
    assert parent.result["failed_shot_ids"] == [shots[1].id]
```

- [ ] **Step 2: 运行测试确认父 job 不会聚合子任务**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_render_batch_flow.py::test_child_render_updates_parent_done_and_failed_summary -v
```

Expected: FAIL，因为父 job 的 `done/status/result` 不会更新。

- [ ] **Step 3: 在 transitions 中补原子聚合 helper**

更新 `backend/app/pipeline/transitions.py`：

```python
async def sync_parent_job_progress(session: AsyncSession, parent_id: str) -> Job:
    from app.domain.models import Job

    parent = await session.get(Job, parent_id)
    children = (
        await session.execute(select(Job).where(Job.parent_id == parent_id).order_by(Job.created_at))
    ).scalars().all()
    done = sum(1 for child in children if child.status in {"succeeded", "failed", "canceled"})
    failed = [child.target_id for child in children if child.status == "failed" and child.target_id]
    succeeded = [child.target_id for child in children if child.status == "succeeded" and child.target_id]

    await update_job_progress(session, parent_id, done=done, total=len(children), progress=int(done * 100 / max(len(children), 1)))
    if done == len(children):
        final_status = "failed" if failed else "succeeded"
        await update_job_progress(session, parent_id, status=final_status, progress=100)
        parent.result = {
            "failed_shot_ids": failed,
            "succeeded_shot_ids": succeeded,
            "pending_shot_ids": [child.target_id for child in children if child.status not in {"succeeded", "failed", "canceled"}],
        }
    return parent
```

- [ ] **Step 4: 在 `render_shot_task` 成功/失败后回写父 job**

在 `backend/app/tasks/ai/render_shot.py` 中，在每个终态分支后追加：

```python
job = await session.get(Job, job_id)
if job is not None and job.parent_id:
    await sync_parent_job_progress(session, job.parent_id)
```

同时保留当前单镜头逻辑不变，保证 M3b 路径不回归。

- [ ] **Step 5: 为批量 ack 路径增加真正可执行的分发器**

在 `backend/app/tasks/ai/render_shot.py` 增加：

```python
async def dispatch_render_batch(parent_job_id: str) -> None:
    async with get_session_factory()() as session:
        children = (
            await session.execute(select(Job).where(Job.parent_id == parent_job_id).order_by(Job.created_at))
        ).scalars().all()
        await update_job_progress(session, parent_job_id, status="running", total=len(children), done=0, progress=0)

        settings = get_settings()
        for child in children:
            render_id = (child.payload or {}).get("render_id")
            shot_id = child.target_id
            if not shot_id or not render_id:
                raise RuntimeError(f"child job {child.id} missing shot_id/render_id")
            if settings.celery_task_always_eager:
                await _render_shot_task(shot_id, render_id, child.id)
            else:
                task = render_shot_task.delay(shot_id, render_id, child.id)
                child.celery_task_id = task.id
        await session.commit()
```

并追加一个 dispatch-failed 兜底 helper，保持和现有单镜头路径一致：

```python
async def mark_render_batch_dispatch_failed(
    db: AsyncSession,
    parent_job_id: str,
    sub_job_ids: list[str],
    error_msg: str,
) -> None:
    await update_job_progress(db, parent_job_id, status="failed", error_msg=error_msg, progress=100)
    for sub_job_id in sub_job_ids:
        await update_job_progress(db, sub_job_id, status="failed", error_msg=f"batch dispatch failed: {error_msg}")
    await db.commit()
```

- [ ] **Step 6: 运行 flow 测试验证批量终态**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_render_batch_flow.py -v
```

Expected: PASS，父 job 在“有失败子任务”的情况下终态为 `failed`，但 `result` 中给出成功/失败子集。

- [ ] **Step 7: Commit**

```bash
git add app/tasks/ai/render_shot.py app/pipeline/transitions.py tests/integration/test_render_batch_flow.py
git commit -m "feat(backend): aggregate child render jobs into render batch parent"
```

## Task 4: 恢复逻辑、项目聚合与 Jobs API 对齐

**Files:**
- Modify: `backend/app/tasks/ai/render_shot.py`
- Modify: `backend/app/infra/volcano_client.py`
- Modify: `backend/app/domain/services/aggregate_service.py`
- Modify: `backend/app/api/projects.py`
- Test: `backend/tests/unit/test_render_batch_recovery.py`
- Test: `backend/tests/integration/test_render_batch_api.py`

- [ ] **Step 1: 先写恢复 helper 的 failing 单测**

在 `backend/tests/unit/test_render_batch_recovery.py` 新增：

```python
def test_should_requeue_or_recover_running_render_job():
    assert choose_render_recovery_action(job_status="running", provider_task_id=None) == "requeue"
    assert choose_render_recovery_action(job_status="running", provider_task_id="task-123") == "provider_lookup"
    assert choose_render_recovery_action(job_status="queued", provider_task_id=None) == "redispatch"
```

- [ ] **Step 2: 运行测试确认 helper 尚不存在**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_render_batch_recovery.py -v
```

Expected: FAIL with import error。

- [ ] **Step 3: 实现恢复决策、provider 回查与父 job 级恢复**

先在 `backend/app/infra/volcano_client.py` 增加 provider 查询接口：

```python
class RealVolcanoClient:
    async def get_image_task(self, provider_task_id: str) -> dict[str, Any]:
        payload = await self._request_json(
            method="GET",
            path=f"/imagex/v1/tasks/{provider_task_id}",
        )
        return {
            "status": payload["data"]["status"],
            "image_url": payload["data"].get("image_url"),
            "error_code": payload["data"].get("error_code"),
            "error_msg": payload["data"].get("error_msg"),
        }
```

再在 `backend/app/tasks/ai/render_shot.py` 增加：

```python
def choose_render_recovery_action(*, job_status: str, provider_task_id: str | None) -> str:
    if job_status == "queued":
        return "redispatch"
    if job_status == "running" and provider_task_id:
        return "provider_lookup"
    if job_status == "running":
        return "requeue"
    return "skip"

async def recover_render_shot_child(session: AsyncSession, child: Job) -> None:
    render_id = (child.payload or {}).get("render_id")
    render = await session.get(ShotRender, render_id) if render_id else None
    action = choose_render_recovery_action(
        job_status=child.status,
        provider_task_id=render.provider_task_id if render else None,
    )

    if action in {"redispatch", "requeue"}:
        render_shot_task.delay(child.target_id, child.payload["render_id"], child.id)
        return

    if action == "provider_lookup":
        client = get_volcano_client()
        provider_state = await client.get_image_task(render.provider_task_id)
        shot = await session.get(StoryboardShot, child.target_id)
        if provider_state["status"] == "succeeded":
            mark_shot_render_succeeded(shot, render, image_url=provider_state["image_url"])
            job = await update_job_progress(session, child.id, status="succeeded", progress=100)
            job.result = {"shot_id": child.target_id, "render_id": render.id, "image_url": provider_state["image_url"]}
            return
        if provider_state["status"] == "failed":
            mark_shot_render_failed(shot, render, error_code=provider_state["error_code"], error_msg=provider_state["error_msg"])
            await update_job_progress(session, child.id, status="failed", error_msg=provider_state["error_msg"], progress=100)
            return

async def recover_render_batch_jobs() -> None:
    async with get_session_factory()() as session:
        parents = (
            await session.execute(
                select(Job).where(Job.kind == "render_batch", Job.status.in_(("queued", "running")))
            )
        ).scalars().all()
        for parent in parents:
            children = (
                await session.execute(select(Job).where(Job.parent_id == parent.id))
            ).scalars().all()
            for child in children:
                await recover_render_shot_child(session, child)
            await sync_parent_job_progress(session, parent.id)
        await session.commit()
```

- [ ] **Step 4: 补齐 jobs 与 project detail 输出字段**

在 `backend/app/api/projects.py` 的 `/projects/{project_id}/jobs` 返回里追加：

```python
"parent_id": j.parent_id,
"target_type": j.target_type,
"target_id": j.target_id,
```

在 `backend/app/domain/services/aggregate_service.py` 对 `render_batch` 项补齐：

```python
{
    **item,
    "sub_job_count": len([j for j in jobs if j.parent_id == item["id"]]),
    "failed_shot_ids": (item.get("result") or {}).get("failed_shot_ids", []),
    "succeeded_shot_ids": (item.get("result") or {}).get("succeeded_shot_ids", []),
    "pending_shot_ids": (item.get("result") or {}).get("pending_shot_ids", []),
}
```

- [ ] **Step 5: 写接口断言，确保前端能看到 `parent_id` 与批量摘要**

在 `backend/tests/integration/test_render_batch_api.py` 追加：

```python
resp = await client.get(f"/api/v1/projects/{project.id}/jobs")
jobs = resp.json()["data"]
assert any(job["kind"] == "render_batch" for job in jobs)
parent = next(job for job in jobs if job["kind"] == "render_batch")
assert any(job["parent_id"] == parent["id"] for job in jobs if job["kind"] == "render_shot")
```

以及：

```python
detail = await client.get(f"/api/v1/projects/{project.id}")
queue = detail.json()["data"]["generationQueue"]
assert any(item["kind"] == "render_batch" and "failed_shot_ids" in item for item in queue)
```

- [ ] **Step 6: 运行恢复与聚合相关测试**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_render_batch_recovery.py tests/integration/test_render_batch_api.py -v
```

Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add app/tasks/ai/render_shot.py app/domain/services/aggregate_service.py app/api/projects.py tests/unit/test_render_batch_recovery.py tests/integration/test_render_batch_api.py
git commit -m "feat(backend): add m3c render batch recovery and aggregate fields"
```

## Task 5: Smoke、README 与回归验证

**Files:**
- Create: `backend/scripts/smoke_m3c.sh`
- Modify: `backend/README.md`

- [ ] **Step 1: 写 smoke 脚本**

创建 `backend/scripts/smoke_m3c.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:?project_id required}"

BATCH="$(curl -s -X POST "http://127.0.0.1:8000/api/v1/projects/${PROJECT_ID}/shots/render" \
  -H 'Content-Type: application/json' \
  -d '{"shot_ids":null,"force_regenerate":false}')"

JOB_ID="$(echo "$BATCH" | jq -r '.data.job_id')"
echo "render_batch job: $JOB_ID"

curl -s "http://127.0.0.1:8000/api/v1/projects/${PROJECT_ID}/jobs" | jq '.data[] | {id,kind,parent_id,status,done,total}'
curl -s "http://127.0.0.1:8000/api/v1/projects/${PROJECT_ID}" | jq '.data | {stage_raw,generationQueue}'
```

- [ ] **Step 2: 在 README 追加 M3c 说明**

更新 `backend/README.md`：

```md
## M3c Batch Rendering

M3c adds:

- `POST /api/v1/projects/{project_id}/shots/render`
- parent `render_batch` job + child `render_shot` jobs
- 60-second idempotent reuse for identical batch requests
- recovery for queued/running batch jobs

Smoke after M3b project reaches `scenes_locked`:

```bash
CELERY_TASK_ALWAYS_EAGER=true uvicorn app.main:app --reload --port 8000
./scripts/smoke_m3c.sh <PROJECT_ID>
```
```

- [ ] **Step 3: 跑本阶段完整验证**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_render_batch_recovery.py tests/integration/test_render_batch_api.py tests/integration/test_render_batch_flow.py -v
```

Expected:

```text
3 files passed
```

- [ ] **Step 4: Commit**

```bash
git add README.md scripts/smoke_m3c.sh
git commit -m "docs(backend): document m3c batch rendering workflow"
```

## Self-Review

- Spec coverage: 已覆盖 §6.3.6 的 `POST /shots/render`、§7.2-§7.4 的幂等/聚合/恢复、§11 的 M3c 非 eager 测试与 smoke。
- Placeholder scan: 所有任务都给了明确文件、命令和关键代码骨架，没有 `TODO/TBD`。
- Type consistency: 统一使用 `parent_id`、`RenderBatchRequest`、`failed_shot_ids`/`succeeded_shot_ids`/`pending_shot_ids`，与前端计划保持一致。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-22-backend-m3c-batch-render.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

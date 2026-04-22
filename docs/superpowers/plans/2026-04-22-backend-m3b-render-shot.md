# Backend M3b: 单镜头渲染草稿 + 确认生成 + 版本历史 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M3a 的角色/场景资产链路之后，把单镜头渲染改成“先生成草稿、用户确认后再生成”的 M3b 流程：后端先为镜头产出建议提示词与参考图列表，前端可临时编辑后再提交确认，随后创建 `shot_renders` 版本、调用火山图像生成、持久化镜头图到 OBS、更新 `storyboards.status/current_render_id`，并提供历史版本列表、切换当前版本、锁定最终版端点。

**Architecture:** M3b 只做单镜头，不做批量聚合 job、不做 worker crash 后 provider 回查、不做导出。后端新增 `POST /render-draft`：根据镜头文案、项目摘要、已锁定场景与角色参考图，自动生成建议 prompt 和 reference images；前端可临时编辑后，再通过 `POST /render` 一次性提交最终 prompt + references。HTTP 层只创建 job 并派发 Celery，ack 复用仓库既有 `GenerateJobAck {job_id, sub_job_ids}` 形状；`render_id` 写入 `Job.payload`，完成后写入 `Job.result`。渲染状态和镜头状态写入集中补到 `pipeline.transitions`；业务编排放在 `domain/services/shot_render_service.py`；任务放在 `tasks/ai/render_shot.py`，沿用 M3a 的 `asset_store.persist_generated_asset(kind="shot")`，并把 Ark 多模态参考请求体按 `docs/integrations/volcengine-ark-api.md` §2.1.3 组装到 provider client。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / Alembic / Celery / Redis / MySQL 8 / pytest-asyncio / respx / httpx。所有命令从 `backend/` 运行并使用 `./.venv/bin/<tool>`。

---

## References

- Backend spec: `docs/superpowers/specs/2026-04-20-backend-mvp-design.md` §4.6、§5.2、§5.3、§6.2、§7.2、§8.1、§13.1、§15 M3b
- M3a backend plan: `docs/superpowers/plans/2026-04-21-backend-m3a-real-volcano-and-assets.md`
- Current M3a baseline files:
  - `backend/app/domain/models/shot_render.py`
  - `backend/app/domain/models/storyboard.py`
  - `backend/app/domain/models/job.py`
  - `backend/app/pipeline/transitions.py`
  - `backend/app/infra/volcano_client.py`
  - `backend/app/infra/asset_store.py`
  - `backend/app/tasks/ai/gen_character_asset.py`

## Scope

**Includes:**
- `POST /api/v1/projects/{project_id}/shots/{shot_id}/render-draft`
- `POST /api/v1/projects/{project_id}/shots/{shot_id}/render`
- `GET /api/v1/projects/{project_id}/shots/{shot_id}/renders`
- `POST /api/v1/projects/{project_id}/shots/{shot_id}/renders/{render_id}/select`
- `POST /api/v1/projects/{project_id}/shots/{shot_id}/lock`
- `ShotRenderService` for render draft generation, confirmed version creation, listing, selection, lock guards, and prompt snapshots
- `render_shot` Celery task for one shot, one version, one `Job`
- Async ack reuses `GenerateJobAck` and returns only `{job_id, sub_job_ids: []}`; `render_id` lives in job payload/result and render history.
- Pipeline helpers for `storyboards.status` and `shot_renders.status`
- Aggregated project detail updates for `generationQueue` and `generationNotes`
- `scripts/smoke_m3b.sh`

**Excludes:**
- `POST /projects/{id}/shots/render` batch rendering and parent/sub-job aggregation. That stays M3c.
- Error-category retry matrix beyond current `RealVolcanoClient` retry behavior. M3b stores `error_code/error_msg`; M3c hardens retry policy.
- Worker crash provider回查 via `provider_task_id`. M3b keeps the column and writes null unless the provider exposes a task id.
- Auto-start rendering without user confirmation. M3b 必须先产出 draft，只有前端确认后才创建 render job。
- 通用“镜头绑定场景”关系编辑。M3b 不再要求用户在场景页手动绑定镜头；render draft 由后端根据镜头文案、已锁定场景和任务上下文自动挑选参考图。
- FFmpeg export and `export_shot_snapshots`. That stays M4.
- Frontend implementation. This plan only guarantees backend contract readiness.

## Current Baseline Notes

- The worktree is dirty and already contains M3a changes. Implementers must not revert unrelated edits.
- `shot_renders` table and ORM model already exist from M2, but the table is not used by business code yet.
- `storyboards.current_render_id` intentionally has no DB FK because of the circular dependency noted in M2. M3b enforces ownership in service code.
- `JOB_KIND_VALUES` already contains `render_shot` and `render_batch`; M3b uses only `render_shot`.
- `asset_store.persist_generated_asset` already accepts `kind="shot"` and returns an OBS object key.
- Current `RealVolcanoClient.image_generations` accepts prompt-only generation. This plan extends it so `render_shot` can submit Ark multi-modal `content[]` with `reference_image` entries and stable OBS URLs / `asset://...` references.

## File Structure

**Create:**

```text
backend/app/api/shots.py
backend/app/domain/schemas/shot_render.py
backend/app/domain/services/shot_render_service.py
backend/app/tasks/ai/render_shot.py
backend/tests/unit/test_shot_render_transitions.py
backend/tests/integration/test_shot_render_api.py
backend/tests/integration/test_render_shot_flow.py
backend/scripts/smoke_m3b.sh
```

**Modify:**

```text
backend/app/main.py
backend/app/api/projects.py
backend/app/domain/schemas/__init__.py
backend/app/domain/services/__init__.py
backend/app/domain/services/aggregate_service.py
backend/app/pipeline/transitions.py
backend/app/pipeline/storyboard_states.py
backend/app/pipeline/__init__.py
backend/app/tasks/ai/__init__.py
backend/app/infra/volcano_client.py
backend/README.md
```

## Task 1: Pipeline Render Transitions

**Files:**
- Modify: `backend/app/pipeline/transitions.py`
- Modify: `backend/app/pipeline/storyboard_states.py`
- Modify: `backend/app/pipeline/__init__.py`
- Modify: `backend/tests/unit/test_storyboard_states.py`
- Test: `backend/tests/unit/test_shot_render_transitions.py`

- [ ] **Step 1: Write failing transition tests**

Create `backend/tests/unit/test_shot_render_transitions.py`:

```python
import pytest

from app.pipeline.transitions import (
    InvalidTransition,
    mark_shot_generating,
    mark_shot_locked,
    mark_shot_render_failed,
    mark_shot_render_running,
    mark_shot_render_succeeded,
    select_shot_render_version,
)


class Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_mark_shot_render_running_from_queued():
    render = Obj(status="queued", error_code=None, error_msg=None)
    mark_shot_render_running(render)
    assert render.status == "running"


def test_mark_shot_render_succeeded_updates_render_and_shot():
    shot = Obj(id="shot1", status="generating", current_render_id=None)
    render = Obj(id="render1", status="running", image_url=None, finished_at=None)
    mark_shot_render_succeeded(shot, render, image_url="projects/p/shot/shot1/v1.png")
    assert render.status == "succeeded"
    assert render.image_url == "projects/p/shot/shot1/v1.png"
    assert render.finished_at is not None
    assert shot.status == "succeeded"
    assert shot.current_render_id == "render1"


def test_mark_shot_render_failed_updates_render_and_shot():
    shot = Obj(status="generating")
    render = Obj(status="running", error_code=None, error_msg=None, finished_at=None)
    mark_shot_render_failed(shot, render, error_code="content_filter", error_msg="blocked")
    assert render.status == "failed"
    assert render.error_code == "content_filter"
    assert render.error_msg == "blocked"
    assert render.finished_at is not None
    assert shot.status == "failed"


def test_mark_shot_locked_requires_succeeded_or_locked():
    mark_shot_locked(Obj(status="succeeded"))
    mark_shot_locked(Obj(status="locked"))
    with pytest.raises(InvalidTransition):
        mark_shot_locked(Obj(status="pending"))


def test_select_shot_render_version_requires_succeeded_render():
    shot = Obj(status="failed", current_render_id=None)
    render = Obj(id="render1", status="succeeded")
    select_shot_render_version(shot, render)
    assert shot.status == "succeeded"
    assert shot.current_render_id == "render1"

    with pytest.raises(InvalidTransition):
        select_shot_render_version(Obj(status="failed"), Obj(id="render2", status="failed"))
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_shot_render_transitions.py -v
```

Expected: fail with import errors for the new transition helpers.

- [ ] **Step 3: Implement transition helpers**

First extend `backend/app/pipeline/storyboard_states.py` so selecting a successful historical render can recover a failed shot without bypassing the storyboard state machine:

```python
STORYBOARD_ALLOWED_TRANSITIONS: dict[StoryboardStatus, set[StoryboardStatus]] = {
    StoryboardStatus.PENDING: {StoryboardStatus.GENERATING},
    StoryboardStatus.GENERATING: {StoryboardStatus.SUCCEEDED, StoryboardStatus.FAILED},
    StoryboardStatus.SUCCEEDED: {StoryboardStatus.LOCKED, StoryboardStatus.GENERATING},
    StoryboardStatus.FAILED: {StoryboardStatus.GENERATING, StoryboardStatus.SUCCEEDED},
    StoryboardStatus.LOCKED: set(),
}
```

Update the top-level imports in `backend/app/pipeline/transitions.py`, then add the helpers below:

```python
from datetime import datetime

from app.pipeline.storyboard_states import StoryboardStatus, is_storyboard_transition_allowed


def _set_storyboard_status(shot: object, target: StoryboardStatus, reason: str) -> None:
    current = StoryboardStatus(getattr(shot, "status"))
    if current == target:
        return
    if not is_storyboard_transition_allowed(current, target):
        raise InvalidTransition(current.value, target.value, reason)
    shot.status = target.value


def mark_shot_generating(shot: object) -> None:
    _set_storyboard_status(shot, StoryboardStatus.GENERATING, "当前镜头状态不可发起单镜头渲染")


def mark_shot_render_running(render: object) -> None:
    current = getattr(render, "status")
    if current != "queued":
        raise InvalidTransition(current, "running", "shot_render 只能 queued → running")
    render.status = "running"
    render.error_code = None
    render.error_msg = None


def mark_shot_render_succeeded(shot: object, render: object, *, image_url: str) -> None:
    current = getattr(render, "status")
    if current != "running":
        raise InvalidTransition(current, "succeeded", "shot_render 只能 running → succeeded")
    render.status = "succeeded"
    render.image_url = image_url
    render.finished_at = datetime.utcnow()
    _set_storyboard_status(shot, StoryboardStatus.SUCCEEDED, "当前镜头状态不可标记渲染成功")
    shot.current_render_id = render.id


def mark_shot_render_failed(
    shot: object,
    render: object,
    *,
    error_code: str,
    error_msg: str,
) -> None:
    current = getattr(render, "status")
    if current not in {"queued", "running"}:
        raise InvalidTransition(current, "failed", "shot_render 只能 queued/running → failed")
    render.status = "failed"
    render.error_code = error_code
    render.error_msg = error_msg
    render.finished_at = datetime.utcnow()
    _set_storyboard_status(shot, StoryboardStatus.FAILED, "当前镜头状态不可标记渲染失败")


def mark_shot_locked(shot: object) -> None:
    _set_storyboard_status(shot, StoryboardStatus.LOCKED, "只有 succeeded 镜头可锁定最终版")


def select_shot_render_version(shot: object, render: object) -> None:
    current = getattr(render, "status")
    if current != "succeeded":
        raise InvalidTransition(current, "select_render", "只能选择 succeeded 的渲染版本")
    shot.current_render_id = render.id
    _set_storyboard_status(shot, StoryboardStatus.SUCCEEDED, "当前镜头状态不可切换到成功版本")
```

Update `backend/app/pipeline/__init__.py` to export the six new helpers explicitly:

```python
from .transitions import (
    mark_shot_generating,
    mark_shot_locked,
    mark_shot_render_failed,
    mark_shot_render_running,
    mark_shot_render_succeeded,
    select_shot_render_version,
)
```

Also append to `backend/tests/unit/test_storyboard_states.py` so the new legal recovery edge is covered by the existing state-machine test file:

```python
def test_storyboard_failed_can_transition_to_succeeded_for_version_selection():
    assert is_storyboard_transition_allowed(StoryboardStatus.FAILED, StoryboardStatus.SUCCEEDED) is True
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_shot_render_transitions.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/transitions.py backend/app/pipeline/storyboard_states.py backend/app/pipeline/__init__.py backend/tests/unit/test_shot_render_transitions.py backend/tests/unit/test_storyboard_states.py
git commit -m "feat(backend): add shot render transition helpers  (Task M3b-1)"
```

## Task 2: Shot Render Draft / Submit Schemas

**Files:**
- Create: `backend/app/domain/schemas/shot_render.py`
- Modify: `backend/app/domain/schemas/__init__.py`
- Test: `backend/tests/unit/test_schema_validation.py`

- [ ] **Step 1: Add schema tests**

Append to `backend/tests/unit/test_schema_validation.py`:

```python
from app.domain.schemas import GenerateJobAck
from app.domain.schemas.shot_render import RenderDraftRead, RenderSubmitRequest, RenderVersionRead


def test_single_render_ack_reuses_generate_job_ack_shape():
    ack = GenerateJobAck(job_id="01HJOB", sub_job_ids=[])
    assert ack.model_dump() == {"job_id": "01HJOB", "sub_job_ids": []}


def test_render_draft_read_supports_prompt_and_references():
    item = RenderDraftRead(
        shot_id="01HSHOT",
        prompt="图片1中的宫门，图片2中的主角，电影感低机位。",
        references=[
            {
                "id": "scene-1",
                "kind": "scene",
                "source_id": "scene01",
                "name": "秦昭入宫",
                "image_url": "https://static.example.com/scene.png",
                "reason": "镜头描述提到宫门",
            }
        ],
    )
    assert item.references[0].kind == "scene"


def test_render_submit_request_accepts_frontend_confirm_payload():
    item = RenderSubmitRequest(
        prompt="图片1中的宫门，图片2中的主角，电影感低机位。",
        references=[
            {
                "id": "scene-1",
                "kind": "scene",
                "source_id": "scene01",
                "name": "秦昭入宫",
                "image_url": "https://static.example.com/scene.png",
            }
        ],
    )
    assert item.references[0].source_id == "scene01"


def test_render_version_read_accepts_prompt_snapshot():
    item = RenderVersionRead(
        id="01HRENDER",
        shot_id="01HSHOT",
        version_no=2,
        status="succeeded",
        prompt_snapshot={"shot": {"title": "镜头 1"}},
        image_url="https://static.example.com/projects/p/shot/s/v2.png",
        error_code=None,
        error_msg=None,
        created_at="2026-04-22T00:00:00",
        finished_at="2026-04-22T00:01:00",
        is_current=True,
    )
    assert item.version_no == 2
    assert item.is_current is True
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_schema_validation.py -v
```

Expected: fail because `app.domain.schemas.shot_render` does not exist.

- [ ] **Step 3: Create schemas**

Do **not** create a render-specific ack schema. Single render endpoints reuse `GenerateJobAck` from the existing character/scene async contract.

Create `backend/app/domain/schemas/shot_render.py`:

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RenderVersionRead(BaseModel):
    id: str
    shot_id: str
    version_no: int
    status: str
    prompt_snapshot: dict[str, Any] | None = None
    image_url: str | None = None
    provider_task_id: str | None = None
    error_code: str | None = None
    error_msg: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    is_current: bool = False


class RenderDraftReferenceRead(BaseModel):
    id: str
    kind: str
    source_id: str
    name: str
    image_url: str
    reason: str


class RenderDraftRead(BaseModel):
    shot_id: str
    prompt: str
    references: list[RenderDraftReferenceRead]


class RenderSubmitReference(BaseModel):
    id: str
    kind: str
    source_id: str
    name: str
    image_url: str


class RenderSubmitRequest(BaseModel):
    prompt: str
    references: list[RenderSubmitReference]
```

Update `backend/app/domain/schemas/__init__.py`:

```python
from .shot_render import (
    RenderDraftRead,
    RenderSubmitRequest,
    RenderVersionRead,
)
```

Also append `"RenderDraftRead"`, `"RenderSubmitRequest"`, and `"RenderVersionRead"` to the existing `__all__` list in that file.

- [ ] **Step 4: Run tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_schema_validation.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/schemas/shot_render.py backend/app/domain/schemas/__init__.py backend/tests/unit/test_schema_validation.py
git commit -m "feat(backend): add shot render response schemas  (Task M3b-2)"
```

## Task 3: ShotRenderService — Draft 生成与确认提交

**Files:**
- Create: `backend/app/domain/services/shot_render_service.py`
- Modify: `backend/app/domain/services/__init__.py`
- Test: `backend/tests/integration/test_shot_render_api.py`

- [ ] **Step 1: Write service/API-facing integration tests**

Create `backend/tests/integration/test_shot_render_api.py` with a seeding helper matching existing integration tests:

```python
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
    session.add_all([project, scene, character, shot])
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
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_render_api.py -v
```

Expected: fail because `ShotRenderService` does not exist.

- [ ] **Step 3: Implement service**

Create `backend/app/domain/services/shot_render_service.py`:

```python
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.domain.models import Character, Project, Scene, ShotRender, StoryboardShot
from app.domain.schemas.shot_render import RenderSubmitRequest
from app.infra.asset_store import build_asset_url
from app.pipeline.states import ProjectStageRaw
from app.pipeline.transitions import (
    InvalidTransition,
    mark_shot_generating,
    mark_shot_locked,
    select_shot_render_version,
)


RENDERABLE_STAGES = {
    ProjectStageRaw.SCENES_LOCKED.value,
    ProjectStageRaw.RENDERING.value,
}


class ShotRenderService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_project(self, project_id: str) -> Project:
        project = await self.session.get(Project, project_id)
        if project is None:
            raise ApiError(40401, "项目不存在", http_status=404)
        return project

    async def _get_shot(self, project_id: str, shot_id: str) -> StoryboardShot:
        shot = await self.session.get(StoryboardShot, shot_id)
        if shot is None or shot.project_id != project_id:
            raise ApiError(40401, "分镜不存在", http_status=404)
        return shot

    async def build_render_draft(self, project_id: str, shot_id: str) -> dict:
        project = await self._get_project(project_id)
        if project.stage not in RENDERABLE_STAGES:
            raise InvalidTransition(project.stage, "render_draft", "只有 scenes_locked/rendering 阶段允许生成镜头草稿")

        shot = await self._get_shot(project_id, shot_id)
        scenes = (
            await self.session.execute(
                select(Scene).where(Scene.project_id == project_id, Scene.locked.is_(True)).order_by(Scene.updated_at.desc())
            )
        ).scalars().all()
        characters = (
            await self.session.execute(
                select(Character).where(Character.project_id == project_id).order_by(Character.is_protagonist.desc(), Character.created_at)
            )
        ).scalars().all()
        references = self._select_references(shot, scenes, characters)
        prompt = self._build_draft_prompt(shot, references)
        return {"shot_id": shot.id, "prompt": prompt, "references": references}

    async def create_render_version(
        self,
        project_id: str,
        shot_id: str,
        payload: RenderSubmitRequest,
    ) -> ShotRender:
        project = await self._get_project(project_id)
        if project.stage not in RENDERABLE_STAGES:
            raise InvalidTransition(project.stage, "render_shot", "只有 scenes_locked/rendering 阶段允许单镜头渲染")

        shot = (
            await self.session.execute(
                select(StoryboardShot)
                .where(StoryboardShot.id == shot_id, StoryboardShot.project_id == project_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if shot is None:
            raise ApiError(40401, "分镜不存在", http_status=404)
        if not payload.references:
            raise ValueError("至少需要 1 张参考图后才能确认生成")

        max_version = (
            await self.session.execute(
                select(func.max(ShotRender.version_no)).where(ShotRender.shot_id == shot_id)
            )
        ).scalar()
        render = ShotRender(
            shot_id=shot.id,
            version_no=(max_version or 0) + 1,
            status="queued",
            prompt_snapshot={
                "prompt": payload.prompt,
                "references": [item.model_dump() for item in payload.references],
                "shot": {
                    "id": shot.id,
                    "idx": shot.idx,
                    "title": shot.title,
                    "description": shot.description,
                    "detail": shot.detail,
                    "tags": shot.tags or [],
                },
            },
        )
        self.session.add(render)
        mark_shot_generating(shot)
        await self.session.flush()
        return render

    def _asset_ref(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("http://") or value.startswith("https://") or value.startswith("asset://"):
            return value
        return build_asset_url(value)

    def _select_references(self, shot: StoryboardShot, scenes: list[Scene], characters: list[Character]) -> list[dict]:
        return [
            *[
                {
                    "id": f"scene:{scene.id}",
                    "kind": "scene",
                    "source_id": scene.id,
                    "name": scene.name,
                    "image_url": self._asset_ref(scene.reference_image_url),
                    "reason": "镜头文案命中该场景",
                }
                for scene in scenes
                if self._asset_ref(scene.reference_image_url)
            ][:1],
            *[
                {
                    "id": f"character:{c.id}",
                    "kind": "character",
                    "source_id": c.id,
                    "name": c.name,
                    "image_url": self._asset_ref(c.reference_image_url),
                    "reason": "主角/出场角色一致性参考",
                }
                for c in characters
                if self._asset_ref(c.reference_image_url)
            ][:2],
        ]

    def _build_draft_prompt(self, shot: StoryboardShot, references: list[dict]) -> str:
        return (
            f"镜头标题：{shot.title}\n"
            f"镜头描述：{shot.description}\n"
            f"镜头细节：{shot.detail or ''}\n"
            "请参考图片1中的主场景与后续图片中的角色形象，生成一张竖屏漫剧静帧，电影感构图，主体清晰。"
        )

    async def list_renders(self, project_id: str, shot_id: str) -> list[ShotRender]:
        await self._get_shot(project_id, shot_id)
        return (
            await self.session.execute(
                select(ShotRender).where(ShotRender.shot_id == shot_id).order_by(ShotRender.version_no.desc())
            )
        ).scalars().all()

    async def select_render(self, project_id: str, shot_id: str, render_id: str) -> StoryboardShot:
        shot = await self._get_shot(project_id, shot_id)
        render = await self.session.get(ShotRender, render_id)
        if render is None or render.shot_id != shot.id:
            raise ApiError(40401, "渲染版本不存在", http_status=404)
        select_shot_render_version(shot, render)
        await self.session.flush()
        return shot

    async def lock_shot(self, project_id: str, shot_id: str) -> StoryboardShot:
        project = await self._get_project(project_id)
        if project.stage not in {ProjectStageRaw.RENDERING.value, ProjectStageRaw.READY_FOR_EXPORT.value}:
            raise InvalidTransition(project.stage, "lock_shot", "只有 rendering/ready_for_export 阶段允许锁定镜头")
        shot = await self._get_shot(project_id, shot_id)
        if not shot.current_render_id:
            raise ValueError("镜头没有当前渲染版本，不能锁定")
        mark_shot_locked(shot)
        await self.session.flush()
        return shot
```

The `SELECT ... FOR UPDATE` on the target storyboard row is still required. It serializes concurrent confirm clicks for the same shot so `max(version_no) + 1` cannot race against `uq_shot_renders_shot_version`.

Update `backend/app/domain/services/__init__.py`:

```python
from .shot_render_service import ShotRenderService
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_render_api.py::test_build_render_draft_returns_prompt_and_references tests/integration/test_shot_render_api.py::test_create_render_version_from_confirmed_payload_increments_version -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/services/shot_render_service.py backend/app/domain/services/__init__.py backend/tests/integration/test_shot_render_api.py
git commit -m "feat(backend): add shot render service  (Task M3b-3)"
```

## Task 4: Single Render Celery Task + Ark 多模态参考

**Files:**
- Create: `backend/app/tasks/ai/render_shot.py`
- Modify: `backend/app/tasks/ai/__init__.py`
- Test: `backend/tests/integration/test_render_shot_flow.py`

- [ ] **Step 1: Write render task integration test**

Create `backend/tests/integration/test_render_shot_flow.py`:

```python
import pytest

from app.domain.models import Job, ShotRender, StoryboardShot
from app.domain.schemas.shot_render import RenderSubmitRequest
from app.domain.services.job_service import JobService
from app.domain.services.shot_render_service import ShotRenderService
from app.tasks.ai.render_shot import _render_shot_task

from tests.integration.test_shot_render_api import seed_renderable_project


@pytest.mark.asyncio
async def test_render_shot_task_persists_image_and_updates_status(client, db_session, monkeypatch):
    project, shot = await seed_renderable_project(db_session)
    render = await ShotRenderService(db_session).create_render_version(
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
                    "image_url": "https://static.example.com/scene.png",
                }
            ],
        ),
    )
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"render_id": render.id},
    )
    await db_session.commit()

    class FakeClient:
        async def image_generations(self, model, prompt, **kwargs):
            assert kwargs["size"] == "1024x1792"
            return {"data": [{"url": "https://volcano.example/tmp-shot.png"}]}

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        assert kind == "shot"
        assert url == "https://volcano.example/tmp-shot.png"
        return f"projects/{project_id}/shot/{shot.id}/v1.png"

    monkeypatch.setattr("app.tasks.ai.render_shot.get_volcano_client", lambda: FakeClient())
    monkeypatch.setattr("app.tasks.ai.render_shot.persist_generated_asset", fake_persist_generated_asset)

    await _render_shot_task(shot.id, render.id, job.id)

    db_session.expire_all()
    saved_render = await db_session.get(ShotRender, render.id)
    saved_shot = await db_session.get(StoryboardShot, shot.id)
    saved_job = await db_session.get(Job, job.id)

    assert saved_render.status == "succeeded"
    assert saved_render.image_url.endswith("/v1.png")
    assert saved_shot.status == "succeeded"
    assert saved_shot.current_render_id == render.id
    assert saved_job.status == "succeeded"
    assert saved_job.progress == 100
    assert saved_job.result["render_id"] == render.id
```

- [ ] **Step 2: Run failing test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_render_shot_flow.py -v
```

Expected: fail because `app.tasks.ai.render_shot` does not exist.

- [ ] **Step 3: Implement task**

Create `backend/app/tasks/ai/render_shot.py`:

```python
import asyncio
import logging

from app.config import get_settings
from app.domain.models import Job, ShotRender, StoryboardShot
from app.infra.asset_store import persist_generated_asset
from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.infra.volcano_errors import (
    VolcanoContentFilterError,
    VolcanoError,
    VolcanoRateLimitError,
    VolcanoServerError,
    VolcanoTimeoutError,
)
from app.pipeline.transitions import (
    mark_shot_render_failed,
    mark_shot_render_running,
    mark_shot_render_succeeded,
    update_job_progress,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _build_render_prompt(snapshot: dict) -> str:
    shot = snapshot.get("shot") or {}
    scene = snapshot.get("scene") or {}
    characters = snapshot.get("characters") or []
    character_lines = "\n".join(
        f"- {c.get('name')}: {c.get('description')}" for c in characters if c.get("name")
    )
    return (
        "生成一张竖屏漫剧镜头静帧，按文字描述保持角色与场景风格连续。\n"
        f"镜头标题:{shot.get('title', '')}\n"
        f"镜头描述:{shot.get('description', '')}\n"
        f"镜头细节:{shot.get('detail', '')}\n"
        f"场景:{scene.get('name', '')} {scene.get('description', '')}\n"
        f"角色:\n{character_lines}\n"
        "画面要求:电影感构图，清晰主体，适合 9:16 短视频。"
    )


def _extract_image_url(resp: object) -> str:
    if isinstance(resp, dict):
        return resp["data"][0]["url"]
    return resp.data[0].url


def _volcano_error_code(exc: VolcanoError) -> str:
    if isinstance(exc, VolcanoContentFilterError):
        return "content_filter"
    if isinstance(exc, VolcanoRateLimitError):
        return "rate_limit"
    if isinstance(exc, VolcanoTimeoutError):
        return "timeout"
    if isinstance(exc, VolcanoServerError):
        return "server_error"
    return "volcano_error"


async def _render_shot_task(shot_id: str, render_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        render = await session.get(ShotRender, render_id)
        shot = await session.get(StoryboardShot, shot_id)
        if render is None or shot is None or render.shot_id != shot.id:
            job = await session.get(Job, job_id)
            if job is not None:
                await update_job_progress(session, job_id, status="failed", error_msg="shot/render 不存在")
                await session.commit()
            return

        if render.status == "succeeded":
            job = await session.get(Job, job_id)
            if job is not None and job.status == "queued":
                await update_job_progress(session, job_id, status="running", progress=max(job.progress, 95))
            if job is not None and job.status in {"queued", "running"}:
                job = await update_job_progress(session, job_id, status="succeeded", progress=100)
                job.result = {"shot_id": shot.id, "render_id": render.id, "image_url": render.image_url}
                await session.commit()
            return
        if render.status == "failed":
            job = await session.get(Job, job_id)
            if job is not None and job.status in {"queued", "running"}:
                await update_job_progress(session, job_id, status="failed", error_msg=render.error_msg or "render failed")
                await session.commit()
            return
        if render.status == "running":
            job = await session.get(Job, job_id)
            if job is not None and job.status == "queued":
                await update_job_progress(session, job_id, status="running", progress=max(job.progress, 5))
                await session.commit()
            return

        try:
            await update_job_progress(session, job_id, status="running", progress=5)
            mark_shot_render_running(render)
            await session.commit()

            settings = get_settings()
            client = get_volcano_client()
            snapshot = render.prompt_snapshot or {}
            # M3b 统一把 confirmed references 作为 provider-consumable refs 传入；
            # service 层已经把 object key 归一成公网 URL / asset:// 引用，这里不再传裸 key。
            response = await client.image_generations(
                model=settings.ark_image_model,
                prompt=snapshot["prompt"],
                references=[item["image_url"] for item in snapshot.get("references", [])],
                n=1,
                size=getattr(settings, "ark_shot_image_size", "1024x1792"),
            )
            await update_job_progress(session, job_id, progress=55)
            await session.commit()

            temp_url = _extract_image_url(response)
            object_key = await persist_generated_asset(
                url=temp_url,
                project_id=shot.project_id,
                kind="shot",
                ext="png",
            )
            mark_shot_render_succeeded(shot, render, image_url=object_key)
            job = await update_job_progress(session, job_id, status="succeeded", progress=100)
            job.result = {"shot_id": shot.id, "render_id": render.id, "image_url": object_key}
            await session.commit()
        except VolcanoError as exc:
            mark_shot_render_failed(shot, render, error_code=_volcano_error_code(exc), error_msg=str(exc))
            await update_job_progress(session, job_id, status="failed", error_msg=str(exc))
            await session.commit()
        except Exception as exc:
            logger.exception("render_shot failed")
            mark_shot_render_failed(shot, render, error_code="internal_error", error_msg=str(exc))
            await update_job_progress(session, job_id, status="failed", error_msg=str(exc))
            await session.commit()


@celery_app.task(name="app.tasks.ai.render_shot.render_shot")
def render_shot(shot_id: str, render_id: str, job_id: str) -> None:
    asyncio.run(_render_shot_task(shot_id, render_id, job_id))
```

Also update `backend/app/infra/volcano_client.py` so `image_generations()` can accept render-draft confirmed references and emit Ark-compatible multi-modal `content[]`:

```python
async def image_generations(
    self,
    *,
    model: str,
    prompt: str,
    references: list[str] | None = None,
    n: int = 1,
    size: str | None = None,
) -> dict:
    if references:
        content = [{"type": "text", "text": prompt}]
        for ref in references:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": ref},
                    "role": "reference_image",
                }
            )
        body = {"model": model, "content": content, "response_format": "url"}
    else:
        body = {"model": model, "prompt": prompt, "response_format": "url"}
    if size:
        body["size"] = size
    if n != 1:
        body["n"] = n
    ...
```

Update `backend/app/tasks/ai/__init__.py`:

```python
from .render_shot import render_shot
```

Make sure `__all__` includes `"render_shot"`. The existing `celery_app.include=["app.tasks.ai"]` can keep working once the import is added.

`ark_shot_image_size` is optional during M3b; if the setting does not exist, the task falls back to `"1024x1792"`. Before real-provider smoke, verify the configured size is accepted by Ark for reference-image generation. If not, set `ARK_SHOT_IMAGE_SIZE`/`ark_shot_image_size` to a provider-approved 9:16 size and add the setting in `app/config.py` as part of this task.

- [ ] **Step 4: Run render task test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_render_shot_flow.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/ai/render_shot.py backend/app/tasks/ai/__init__.py backend/tests/integration/test_render_shot_flow.py
git commit -m "feat(backend): add single shot render task  (Task M3b-4)"
```

## Task 5: Shots API

**Files:**
- Create: `backend/app/api/shots.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_shot_render_api.py`

- [ ] **Step 1: Add API tests**

Append to `backend/tests/integration/test_shot_render_api.py`:

```python
@pytest.mark.asyncio
async def test_post_render_draft_returns_prompt_and_references(client, db_session, monkeypatch):
    project, shot = await seed_renderable_project(db_session)
    resp = await client.post(f"/api/v1/projects/{project.id}/shots/{shot.id}/render-draft")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["shot_id"] == shot.id
    assert data["prompt"]
    assert data["references"]


@pytest.mark.asyncio
async def test_post_single_shot_render_returns_job_and_render(client, db_session, monkeypatch):
    project, shot = await seed_renderable_project(db_session)

    class FakeTask:
        id = "celery-render-1"

    monkeypatch.setattr("app.api.shots.render_shot.delay", lambda *args: FakeTask())

    resp = await client.post(
        f"/api/v1/projects/{project.id}/shots/{shot.id}/render",
        json={
            "prompt": "图片1中的宫门，图片2中的主角，电影感低机位。",
            "references": [
                {
                    "id": "scene-1",
                    "kind": "scene",
                    "source_id": "scene01",
                    "name": "长安殿",
                    "image_url": "projects/p/scene/1.png",
                }
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["job_id"]
    assert body["sub_job_ids"] == []

    job = await db_session.get(Job, body["job_id"])
    render = await db_session.get(ShotRender, job.payload["render_id"])
    assert render.status == "queued"
    assert render.version_no == 1


@pytest.mark.asyncio
async def test_post_single_shot_render_uses_eager_branch_without_delay(client, db_session, monkeypatch, settings):
    project, shot = await seed_renderable_project(db_session)
    settings.celery_task_always_eager = True

    async def fake_render_task(shot_id, render_id, job_id):
        job = await db_session.get(Job, job_id)
        render = await db_session.get(ShotRender, render_id)
        render.status = "succeeded"
        render.image_url = "projects/p/shot/s/v1.png"
        job.status = "succeeded"
        job.progress = 100
        job.result = {"shot_id": shot_id, "render_id": render_id, "image_url": render.image_url}
        await db_session.commit()

    def fail_delay(*args, **kwargs):
        raise AssertionError("eager mode should bypass Celery .delay()")

    monkeypatch.setattr("app.api.shots._render_shot_task", fake_render_task)
    monkeypatch.setattr("app.api.shots.render_shot.delay", fail_delay)

    resp = await client.post(
        f"/api/v1/projects/{project.id}/shots/{shot.id}/render",
        json={
            "prompt": "图片1中的宫门，图片2中的主角，电影感低机位。",
            "references": [
                {
                    "id": "scene-1",
                    "kind": "scene",
                    "source_id": "scene01",
                    "name": "长安殿",
                    "image_url": "projects/p/scene/1.png",
                }
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["sub_job_ids"] == []


@pytest.mark.asyncio
async def test_list_select_and_lock_render(client, db_session):
    project, shot = await seed_renderable_project(db_session)
    render = await ShotRenderService(db_session).create_render_version(
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
    render.status = "succeeded"
    render.image_url = "projects/p/shot/s/v1.png"
    await db_session.commit()

    list_resp = await client.get(f"/api/v1/projects/{project.id}/shots/{shot.id}/renders")
    assert list_resp.status_code == 200
    assert list_resp.json()["data"][0]["is_current"] is False

    select_resp = await client.post(
        f"/api/v1/projects/{project.id}/shots/{shot.id}/renders/{render.id}/select"
    )
    assert select_resp.status_code == 200

    project.stage = "rendering"
    await db_session.commit()
    lock_resp = await client.post(f"/api/v1/projects/{project.id}/shots/{shot.id}/lock")
    assert lock_resp.status_code == 200
    assert lock_resp.json()["data"]["status"] == "locked"
```

- [ ] **Step 2: Run failing API tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_render_api.py -v
```

Expected: fail because `app.api.shots` / `/shots/...` is not implemented yet.

- [ ] **Step 3: Implement router**

Create `backend/app/api/shots.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.envelope import ok
from app.api.errors import ApiError
from app.config import get_settings
from app.deps import get_db
from app.domain.schemas import GenerateJobAck
from app.domain.schemas.shot_render import RenderDraftRead, RenderSubmitRequest, RenderVersionRead
from app.domain.services import JobService, ShotRenderService
from app.infra.asset_store import build_asset_url
from app.pipeline.transitions import InvalidTransition, mark_shot_render_failed, update_job_progress
from app.tasks.ai.render_shot import _render_shot_task, render_shot

router = APIRouter(prefix="/projects/{project_id}/shots", tags=["shots"])


@router.post("/{shot_id}/render-draft")
async def render_draft(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    try:
        draft = await ShotRenderService(db).build_render_draft(project_id, shot_id)
        return ok(RenderDraftRead(**draft).model_dump())
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)
    except ValueError as exc:
        raise ApiError(40901, str(exc), http_status=409)


@router.post("/{shot_id}/render")
async def render_one(
    project_id: str,
    shot_id: str,
    payload: RenderSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = ShotRenderService(db)
        render = await svc.create_render_version(project_id, shot_id, payload)
        job = await JobService(db).create_job(
            project_id=project_id,
            kind="render_shot",
            target_type="shot",
            target_id=shot_id,
            payload={"render_id": render.id, "shot_id": shot_id},
        )
        render_id = render.id
        job_id = job.id
        await db.commit()
        try:
            settings = get_settings()
            if settings.celery_task_always_eager:
                await _render_shot_task(shot_id, render_id, job_id)
            else:
                task = render_shot.delay(shot_id, render_id, job_id)
                job.celery_task_id = task.id
                await db.commit()
        except Exception as exc:
            render = await db.get(ShotRender, render_id)
            shot = await svc._get_shot(project_id, shot_id)
            if render is not None and render.status == "queued":
                mark_shot_render_failed(shot, render, error_code="dispatch_failed", error_msg=f"dispatch failed: {exc}")
            await update_job_progress(db, job_id, status="failed", error_msg=f"dispatch failed: {exc}")
            await db.commit()
            raise
        return ok(GenerateJobAck(job_id=job_id, sub_job_ids=[]).model_dump())
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)
    except ValueError as exc:
        raise ApiError(40901, str(exc), http_status=409)


@router.get("/{shot_id}/renders")
async def list_renders(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    svc = ShotRenderService(db)
    shot = await svc._get_shot(project_id, shot_id)
    renders = await svc.list_renders(project_id, shot_id)
    return ok([
        RenderVersionRead(
            id=item.id,
            shot_id=item.shot_id,
            version_no=item.version_no,
            status=item.status,
            prompt_snapshot=item.prompt_snapshot,
            image_url=build_asset_url(item.image_url),
            provider_task_id=item.provider_task_id,
            error_code=item.error_code,
            error_msg=item.error_msg,
            created_at=item.created_at,
            finished_at=item.finished_at,
            is_current=item.id == shot.current_render_id,
        ).model_dump()
        for item in renders
    ])


@router.post("/{shot_id}/renders/{render_id}/select")
async def select_render(project_id: str, shot_id: str, render_id: str, db: AsyncSession = Depends(get_db)):
    try:
        shot = await ShotRenderService(db).select_render(project_id, shot_id, render_id)
        await db.commit()
        return ok({"shot_id": shot.id, "current_render_id": shot.current_render_id, "status": shot.status})
    except InvalidTransition as exc:
        raise ApiError(40901, str(exc), http_status=409)
    except ValueError as exc:
        raise ApiError(40901, str(exc), http_status=409)


@router.post("/{shot_id}/lock")
async def lock_shot(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    try:
        shot = await ShotRenderService(db).lock_shot(project_id, shot_id)
        await db.commit()
        return ok({"shot_id": shot.id, "status": shot.status, "current_render_id": shot.current_render_id})
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)
    except ValueError as exc:
        raise ApiError(40901, str(exc), http_status=409)
```

Modify `backend/app/main.py` to include the router:

```python
from app.api import shots

app.include_router(shots.router, prefix="/api/v1")
```

- [ ] **Step 4: Run API tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_render_api.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/shots.py backend/app/main.py backend/tests/integration/test_shot_render_api.py
git commit -m "feat(backend): expose single shot render APIs  (Task M3b-5)"
```

## Task 6: Stage Advancement to Rendering and Ready for Export

**Files:**
- Modify: `backend/app/pipeline/transitions.py`
- Modify: `backend/app/domain/services/shot_render_service.py`
- Test: `backend/tests/integration/test_shot_render_api.py`

- [ ] **Step 1: Add stage tests**

Append to `backend/tests/integration/test_shot_render_api.py`:

```python
@pytest.mark.asyncio
async def test_first_render_request_advances_scenes_locked_to_rendering(db_session):
    from app.domain.models import Project
    from app.domain.schemas.shot_render import RenderSubmitRequest
    from app.domain.services.shot_render_service import ShotRenderService

    project, shot = await seed_renderable_project(db_session)
    await ShotRenderService(db_session).create_render_version(
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
    saved = await db_session.get(Project, project.id)
    assert saved.stage == "rendering"


@pytest.mark.asyncio
async def test_locking_all_succeeded_shots_advances_to_ready_for_export(db_session):
    from app.domain.models import Project
    from app.domain.schemas.shot_render import RenderSubmitRequest
    from app.domain.services.shot_render_service import ShotRenderService

    project, shot = await seed_renderable_project(db_session)
    project.stage = "rendering"
    render = await ShotRenderService(db_session).create_render_version(
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
    render.status = "succeeded"
    render.image_url = "projects/p/shot/s/v1.png"
    shot.status = "succeeded"
    shot.current_render_id = render.id
    await db_session.commit()

    await ShotRenderService(db_session).lock_shot(project.id, shot.id)
    saved = await db_session.get(Project, project.id)
    assert saved.stage == "ready_for_export"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_render_api.py::test_first_render_request_advances_scenes_locked_to_rendering tests/integration/test_shot_render_api.py::test_locking_all_succeeded_shots_advances_to_ready_for_export -v
```

Expected: fail because project stage does not advance.

- [ ] **Step 3: Implement advancement helpers**

Add to `backend/app/pipeline/transitions.py`:

```python
def advance_to_rendering(project: Project) -> None:
    current = ProjectStageRaw(project.stage)
    if current == ProjectStageRaw.RENDERING:
        return
    if current != ProjectStageRaw.SCENES_LOCKED:
        raise InvalidTransition(current.value, ProjectStageRaw.RENDERING.value, "只有 scenes_locked 可进入 rendering")
    project.stage = ProjectStageRaw.RENDERING.value


async def advance_to_ready_for_export_if_complete(session: AsyncSession, project: Project) -> bool:
    from app.domain.models import StoryboardShot

    current = ProjectStageRaw(project.stage)
    if current == ProjectStageRaw.READY_FOR_EXPORT:
        return True
    if current != ProjectStageRaw.RENDERING:
        return False
    rows = (
        await session.execute(
            select(StoryboardShot.status).where(StoryboardShot.project_id == project.id)
        )
    ).scalars().all()
    if rows and all(status in {"succeeded", "locked"} for status in rows):
        project.stage = ProjectStageRaw.READY_FOR_EXPORT.value
        return True
    return False
```

Update `ShotRenderService.create_render_version`:

```python
from app.domain.models import Character, Project, Scene, ShotRender, StoryboardShot
from app.pipeline.transitions import (
    InvalidTransition,
    advance_to_ready_for_export_if_complete,
    advance_to_rendering,
    mark_shot_generating,
    mark_shot_locked,
    select_shot_render_version,
)

advance_to_rendering(project)
```

In `create_render_version`, reuse the existing `project = await self._get_project(project_id)` local and insert `advance_to_rendering(project)` immediately after the stage guard passes and before `mark_shot_generating(shot)`. In `lock_shot`, insert this after `mark_shot_locked(shot)` and after flushing the locked status:

```python
await self.session.flush()
project = await self.session.get(Project, project_id)
await advance_to_ready_for_export_if_complete(self.session, project)
```

- [ ] **Step 4: Run stage tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_render_api.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/transitions.py backend/app/domain/services/shot_render_service.py backend/tests/integration/test_shot_render_api.py
git commit -m "feat(backend): advance project through render stages  (Task M3b-6)"
```

## Task 7: Aggregate Detail + Jobs List Rendering Fields

**Files:**
- Modify: `backend/app/domain/services/aggregate_service.py`
- Modify: `backend/app/api/projects.py`
- Test: `backend/tests/integration/test_shot_render_api.py`

- [ ] **Step 1: Add aggregate assertion**

Append to `backend/tests/integration/test_shot_render_api.py` (and ensure the file imports `JobService` alongside `ShotRenderService`):

```python
@pytest.mark.asyncio
async def test_project_detail_includes_current_render_queue_item(client, db_session):
    project, shot = await seed_renderable_project(db_session)
    render = await ShotRenderService(db_session).create_render_version(
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
    render.status = "succeeded"
    render.image_url = "projects/p/shot/s/v1.png"
    shot.status = "succeeded"
    shot.current_render_id = render.id
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"render_id": render.id},
    )
    job.status = "running"
    job.progress = 100
    job.result = {"shot_id": shot.id, "render_id": render.id, "image_url": render.image_url}
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["generationProgress"] == "1 / 1 已完成"
    assert data["generationQueue"][0]["id"] == job.id
    assert data["generationQueue"][0]["kind"] == "render_shot"
    assert data["generationQueue"][0]["progress"] == 100
    assert data["generationQueue"][0]["target_id"] == shot.id
    assert data["generationQueue"][0]["shot_id"] == shot.id
    assert data["generationQueue"][0]["render_id"] == render.id
    assert data["generationQueue"][0]["image_url"].endswith("/v1.png")
    assert data["generationQueue"][0]["error_code"] is None
    assert data["generationQueue"][0]["error_msg"] is None
    assert data["generationNotes"]["input"]


@pytest.mark.asyncio
async def test_project_jobs_list_exposes_target_and_payload_for_render_recovery(client, db_session):
    project, shot = await seed_renderable_project(db_session)
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"shot_id": shot.id, "render_id": "R1"},
    )
    job.status = "running"
    job.progress = 45
    job.done = 45
    job.total = 100
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}/jobs")
    assert resp.status_code == 200
    row = resp.json()["data"][0]
    assert row["id"] == job.id
    assert row["target_id"] == shot.id
    assert row["payload"]["shot_id"] == shot.id
    assert row["payload"]["render_id"] == "R1"
    assert row["error_msg"] is None
```

- [ ] **Step 2: Run failing aggregate test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_render_api.py::test_project_detail_includes_current_render_queue_item -v
```

Expected: fail because `generationQueue` is currently job-based and does not include render fields.

- [ ] **Step 3: Update aggregation**

Modify `AggregateService.get_project_detail`:

```python
import json

from app.domain.models import ShotRender

shot_map = {s.id: s for s in storyboards}
queue_render_ids = [
    item.get("result", {}).get("render_id") or item.get("payload", {}).get("render_id")
    for item in generation_queue
    if item.get("kind") == "render_shot"
]
render_ids = list({rid for rid in [*(s.current_render_id for s in storyboards if s.current_render_id), *queue_render_ids] if rid})
render_map = {}
if render_ids:
    current_renders = (
        await self.session.execute(select(ShotRender).where(ShotRender.id.in_(render_ids)))
    ).scalars().all()
    render_map = {r.id: r for r in current_renders}

latest_render = None
if render_ids:
    latest_render = max(
        (render_map[rid] for rid in render_ids if rid in render_map),
        key=lambda r: r.created_at,
        default=None,
    )
```

Keep the existing job-based `generationQueue` semantics. Do **not** replace it with a storyboard-derived list. M3b enriches `render_shot` job items with `target_id / shot_id / render_id / image_url / version_no / shot_status / error_*`. For in-flight jobs, `render_id` and related metadata must prefer `payload.render_id` before `result.render_id`, otherwise queued/running renders will show up blank until success.

```python
generationNotes={
    "input": "" if latest_render is None else json.dumps(latest_render.prompt_snapshot or {}, ensure_ascii=False, indent=2),
    "suggestion": "可从历史版本中选择当前镜头，或重试失败镜头。",
},
generationQueue=[
    {
        **item,
        "shot_id": item.get("target_id") if item.get("kind") == "render_shot" else None,
        "render_id": (
            item.get("result", {}).get("render_id") or item.get("payload", {}).get("render_id")
            if item.get("kind") == "render_shot"
            else None
        ),
        "image_url": (
            build_asset_url(render_map[resolved_render_id].image_url)
            if item.get("kind") == "render_shot"
            and (resolved_render_id := (item.get("result", {}).get("render_id") or item.get("payload", {}).get("render_id"))) in render_map
            else None
        ),
        "version_no": (
            render_map[resolved_render_id].version_no
            if item.get("kind") == "render_shot"
            and (resolved_render_id := (item.get("result", {}).get("render_id") or item.get("payload", {}).get("render_id"))) in render_map
            else None
        ),
        "shot_status": (
            shot_map[item["target_id"]].status
            if item.get("kind") == "render_shot" and item.get("target_id") in shot_map
            else None
        ),
        "error_code": (
            render_map[resolved_render_id].error_code
            if item.get("kind") == "render_shot"
            and (resolved_render_id := (item.get("result", {}).get("render_id") or item.get("payload", {}).get("render_id"))) in render_map
            else None
        ),
        "error_msg": (
            render_map[resolved_render_id].error_msg or item.get("error_msg")
            if item.get("kind") == "render_shot"
            and (resolved_render_id := (item.get("result", {}).get("render_id") or item.get("payload", {}).get("render_id"))) in render_map
            else None
        ),
    }
    for item in generation_queue
],
```

Also expand `backend/app/api/projects.py:list_project_jobs` so frontend恢复逻辑不再依赖一个被截断的 jobs 列表。至少返回：

```python
return ok([
    {
        "id": j.id,
        "kind": j.kind,
        "status": j.status,
        "progress": j.progress,
        "total": j.total,
        "done": j.done,
        "payload": j.payload,
        "result": j.result,
        "error_msg": j.error_msg,
        "target_type": j.target_type,
        "target_id": j.target_id,
        "created_at": j.created_at,
        "finished_at": j.finished_at,
    }
    for j in jobs
])
```

- [ ] **Step 4: Run aggregate test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_render_api.py::test_project_detail_includes_current_render_queue_item tests/integration/test_shot_render_api.py::test_project_jobs_list_exposes_target_and_payload_for_render_recovery -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/services/aggregate_service.py backend/app/api/projects.py backend/tests/integration/test_shot_render_api.py
git commit -m "feat(backend): include render versions in project detail  (Task M3b-7)"
```

## Task 8: Error Mapping and Regression Coverage

**Files:**
- Modify: `backend/app/api/shots.py`
- Modify: `backend/app/tasks/ai/render_shot.py`
- Test: `backend/tests/integration/test_render_shot_flow.py`

- [ ] **Step 1: Add failure test**

Append to `backend/tests/integration/test_render_shot_flow.py`:

```python
@pytest.mark.asyncio
async def test_render_shot_task_records_volcano_error(client, db_session, monkeypatch):
    from app.infra.volcano_errors import VolcanoContentFilterError

    project, shot = await seed_renderable_project(db_session)
    render = await ShotRenderService(db_session).create_render_version(
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
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"render_id": render.id},
    )
    await db_session.commit()

    class FakeClient:
        async def image_generations(self, model, prompt, **kwargs):
            raise VolcanoContentFilterError("内容违规")

    monkeypatch.setattr("app.tasks.ai.render_shot.get_volcano_client", lambda: FakeClient())

    await _render_shot_task(shot.id, render.id, job.id)

    db_session.expire_all()
    saved_render = await db_session.get(ShotRender, render.id)
    saved_shot = await db_session.get(StoryboardShot, shot.id)
    saved_job = await db_session.get(Job, job.id)
    assert saved_render.status == "failed"
    assert saved_render.error_code == "content_filter"
    assert saved_shot.status == "failed"
    assert saved_job.status == "failed"


@pytest.mark.asyncio
async def test_render_shot_task_is_idempotent_for_succeeded_render(client, db_session, monkeypatch):
    project, shot = await seed_renderable_project(db_session)
    render = await ShotRenderService(db_session).create_render_version(
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
    render.status = "succeeded"
    render.image_url = "projects/p/shot/s/v1.png"
    shot.status = "succeeded"
    shot.current_render_id = render.id
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"render_id": render.id},
    )
    await db_session.commit()

    class ShouldNotCallClient:
        async def image_generations(self, model, prompt, **kwargs):
            raise AssertionError("already succeeded render must not call provider again")

    monkeypatch.setattr("app.tasks.ai.render_shot.get_volcano_client", lambda: ShouldNotCallClient())

    await _render_shot_task(shot.id, render.id, job.id)

    db_session.expire_all()
    saved_render = await db_session.get(ShotRender, render.id)
    saved_job = await db_session.get(Job, job.id)
    assert saved_render.status == "succeeded"
    assert saved_job.status == "succeeded"
    assert saved_job.result["render_id"] == render.id


@pytest.mark.asyncio
async def test_render_shot_task_is_idempotent_for_running_render(client, db_session, monkeypatch):
    project, shot = await seed_renderable_project(db_session)
    render = await ShotRenderService(db_session).create_render_version(
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
    render.status = "running"
    shot.status = "generating"
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot",
        target_type="shot",
        target_id=shot.id,
        payload={"render_id": render.id},
    )
    await db_session.commit()

    class ShouldNotCallClient:
        async def image_generations(self, model, prompt, **kwargs):
            raise AssertionError("running render re-delivery must not call provider again")

    monkeypatch.setattr("app.tasks.ai.render_shot.get_volcano_client", lambda: ShouldNotCallClient())

    await _render_shot_task(shot.id, render.id, job.id)

    db_session.expire_all()
    saved_render = await db_session.get(ShotRender, render.id)
    saved_job = await db_session.get(Job, job.id)
    assert saved_render.status == "running"
    assert saved_job.status == "running"
```

- [ ] **Step 2: Run failure test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_render_shot_flow.py::test_render_shot_task_records_volcano_error -v
```

Expected: pass. `render_shot.py` maps current `VolcanoError` subclasses to stable `shot_renders.error_code` strings; do not add a new `category` property unless the existing M3a error tests are updated at the same time.

- [ ] **Step 3: Normalize API errors**

Ensure `backend/app/api/shots.py` keeps render/lock stage violations as 403 and maps select-version conflicts to 409:

```python
# render_one / lock_shot
except InvalidTransition as exc:
    raise ApiError(40301, str(exc), http_status=403)
except ValueError as exc:
    raise ApiError(40901, str(exc), http_status=409)

# select_render
except InvalidTransition as exc:
    raise ApiError(40901, str(exc), http_status=409)
except ValueError as exc:
    raise ApiError(40901, str(exc), http_status=409)
```

Do not return `40001` for valid requests blocked by render preconditions such as “no references selected” or selecting a failed render; those are business conflicts.

- [ ] **Step 4: Run render API and task tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_render_api.py tests/integration/test_render_shot_flow.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/shots.py backend/app/tasks/ai/render_shot.py backend/tests/integration/test_render_shot_flow.py
git commit -m "feat(backend): harden shot render error handling  (Task M3b-8)"
```

## Task 9: M3b Smoke Script and README

**Files:**
- Create: `backend/scripts/smoke_m3b.sh`
- Modify: `backend/README.md`

- [ ] **Step 1: Create smoke script**

Create `backend/scripts/smoke_m3b.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000/api/v1}"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing command: $1" >&2; exit 1; }
}

need curl
need jq

PROJECT_ID="${1:-}"
SHOT_ID="${2:-}"

if [[ -z "$PROJECT_ID" || -z "$SHOT_ID" ]]; then
  echo "usage: $0 <PROJECT_ID> <SHOT_ID>" >&2
  echo "project must already be at scenes_locked or rendering, and shot should be renderable" >&2
  exit 2
fi

echo "Build render draft..."
DRAFT="$(curl -fsS -X POST "$BASE_URL/projects/$PROJECT_ID/shots/$SHOT_ID/render-draft")"
PROMPT="$(echo "$DRAFT" | jq -r '.data.prompt')"
REFERENCES="$(echo "$DRAFT" | jq -c '.data.references | map({id,kind,source_id,name,image_url})')"

echo "Trigger single shot render..."
ACK="$(curl -fsS -X POST "$BASE_URL/projects/$PROJECT_ID/shots/$SHOT_ID/render" \
  -H 'Content-Type: application/json' \
  -d "{\"prompt\":$(jq -Rn --arg v "$PROMPT" '$v'),\"references\":$REFERENCES}")"
JOB_ID="$(echo "$ACK" | jq -r '.data.job_id')"
echo "job=$JOB_ID"

SUCCEEDED=0
for _ in $(seq 1 90); do
  JOB="$(curl -fsS "$BASE_URL/jobs/$JOB_ID")"
  STATUS="$(echo "$JOB" | jq -r '.data.status')"
  PROGRESS="$(echo "$JOB" | jq -r '.data.progress')"
  echo "status=$STATUS progress=$PROGRESS"
  if [[ "$STATUS" == "succeeded" ]]; then
    SUCCEEDED=1
    break
  fi
  if [[ "$STATUS" == "failed" || "$STATUS" == "canceled" ]]; then
    echo "$JOB" | jq .
    exit 1
  fi
  sleep 2
done

if [[ "$SUCCEEDED" != "1" ]]; then
  echo "render job timed out before success" >&2
  curl -fsS "$BASE_URL/jobs/$JOB_ID" | jq .
  exit 1
fi

JOB="$(curl -fsS "$BASE_URL/jobs/$JOB_ID")"
RENDER_ID="$(echo "$JOB" | jq -r '.data.result.render_id')"
if [[ -z "$RENDER_ID" || "$RENDER_ID" == "null" ]]; then
  echo "job succeeded but did not expose result.render_id" >&2
  echo "$JOB" | jq .
  exit 1
fi
echo "render=$RENDER_ID"

curl -fsS "$BASE_URL/projects/$PROJECT_ID/shots/$SHOT_ID/renders" | jq .
curl -fsS -X POST "$BASE_URL/projects/$PROJECT_ID/shots/$SHOT_ID/renders/$RENDER_ID/select" | jq .
curl -fsS -X POST "$BASE_URL/projects/$PROJECT_ID/shots/$SHOT_ID/lock" | jq .
```

Run:

```bash
cd backend
chmod +x scripts/smoke_m3b.sh
```

- [ ] **Step 2: Update README**

Add a short M3b section to `backend/README.md`:

```markdown
## M3b Single Shot Rendering

M3b adds `render_shot` for one storyboard shot at a time:

- `POST /api/v1/projects/{project_id}/shots/{shot_id}/render-draft`
- `POST /api/v1/projects/{project_id}/shots/{shot_id}/render`
- `GET /api/v1/projects/{project_id}/shots/{shot_id}/renders`
- `POST /api/v1/projects/{project_id}/shots/{shot_id}/renders/{render_id}/select`
- `POST /api/v1/projects/{project_id}/shots/{shot_id}/lock`

`POST /render-draft` returns backend-selected prompt + references for user confirmation. `POST /render` returns the standard async ack shape:

```json
{ "job_id": "01H...", "sub_job_ids": [] }
```

The created `render_id` is stored in `jobs.payload.render_id` and copied to `jobs.result.render_id` when the task succeeds.

Run smoke after M3a has produced a project at `scenes_locked`:

```bash
CELERY_TASK_ALWAYS_EAGER=true uvicorn app.main:app --reload --port 8000
./scripts/smoke_m3b.sh <PROJECT_ID> <SHOT_ID>
```

Batch render remains M3c; export remains M4.
```

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/smoke_m3b.sh backend/README.md
git commit -m "docs(backend): document M3b shot render smoke  (Task M3b-9)"
```

## Task 10: Full Verification

**Files:**
- No source changes unless verification exposes a defect.

- [ ] **Step 1: Run focused unit and integration tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_shot_render_transitions.py tests/unit/test_schema_validation.py tests/integration/test_shot_render_api.py tests/integration/test_render_shot_flow.py -v
```

Expected: pass.

- [ ] **Step 2: Run broader backend safety suite**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/ tests/integration/test_projects_api.py tests/integration/test_storyboards_api.py tests/integration/test_m3a_contract.py -v
```

Expected: pass.

- [ ] **Step 3: Run lint and type-check**

Run:

```bash
cd backend
./.venv/bin/ruff check app tests
./.venv/bin/mypy
```

Expected: both pass.

- [ ] **Step 4: Run smoke**

Start API in a separate shell:

```bash
cd backend
CELERY_TASK_ALWAYS_EAGER=true ./.venv/bin/uvicorn app.main:app --reload --port 8000
```

Run M3a smoke to produce/verify a `scenes_locked` project, then run:

```bash
cd backend
./scripts/smoke_m3b.sh <PROJECT_ID> <SHOT_ID>
```

Expected: render job succeeds, render history lists the new version, select returns current render id, lock returns `status=locked`.

- [ ] **Step 5: Final commit if verification fixes were needed**

```bash
git add backend/app backend/tests backend/scripts backend/README.md
git commit -m "fix(backend): stabilize M3b render verification  (Task M3b-10)"
```

Only run this commit if Step 1-4 required code fixes after Task 9.

## Self-Review Checklist

- Spec coverage:
  - `render-draft` 草稿接口：Task 2 / Task 3 / Task 5
  - `render_shot` single task: Task 4
  - `shot_renders` version table usage: Task 3 and Task 4
  - historical render list: Task 5
  - select current render: Task 5
  - lock final shot: Task 5 and Task 6
  - stage `scenes_locked → rendering → ready_for_export`: Task 6
  - project detail `generationQueue` and `generationNotes`: Task 7
  - smoke verification: Task 9 and Task 10
- M3c exclusions are explicit: batch render, retry matrix hardening, worker crash recovery.
- M4 exclusions are explicit: export and snapshots.
- No direct `project.stage` mutation outside `pipeline.transitions` except inside new transition helpers.
- No direct existing-row `storyboards.status` or `shot_renders.status` mutation outside `pipeline.transitions` except tests arranging state.
- `POST /render-draft` 只产出建议 prompt + references，不启动生成；`POST /render` 才创建 job。
- API route creates a job and returns immediately; no AI call blocks inside HTTP.
- Single render ack uses the existing `GenerateJobAck {job_id, sub_job_ids}` shape; `render_id` is in job payload/result and render history.
- `POST /render` has an eager branch for `CELERY_TASK_ALWAYS_EAGER=true` and does not call `asyncio.run()` through Celery `.delay()` inside an active request loop.
- `version_no` allocation locks the target storyboard row with `SELECT ... FOR UPDATE` before reading `max(version_no)`.
- `generationQueue` stays job-based; render metadata is additive and does not replace the existing queue identity/semantics.
- `_render_shot_task` is idempotent for duplicate delivery when render state is already `running`, `succeeded`, or `failed`.
- M3b 已接入 Ark 多模态参考；`prompt_snapshot` 保存的是用户确认后的 prompt + references，而不是后端未确认草稿。

Plan complete and saved to `docs/superpowers/plans/2026-04-22-backend-m3b-render-shot.md`.

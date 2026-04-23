# Backend Minor: Shot Final Video Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留 `render-draft` 草稿推荐能力的前提下，把单镜头“确认生成静帧”改成“直接提交最终成品视频任务”，后端新增 Seedance 视频任务链路、视频版本历史、当前版本切换与锁定能力，并把视频状态聚合到项目详情接口供前端消费。

**Architecture:** 继续保留 `POST /render-draft`，它只负责推荐镜头提示词与参考图，不落库、不创建 provider 任务。真正生成成品时，新增 `POST /video` 端点，由后端把前端当前 textarea 中的提示词原样作为 `content[0].text`，并把当前参考图顺序映射为 Ark Seedance 的多参考图视频模式。本流程固定只走 `reference_image` 路径，不支持 `first_frame` / `last_frame` 模式，也不做自动 prompt 改写。视频任务使用独立的 `ShotVideoRender` 版本表和 `render_shot_video` job kind，Celery 明确路由到 `video` 队列；成功后立即把 `video_url` / `last_frame_url` 回源到自有存储，再写回聚合详情与历史版本接口。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / Alembic / Celery / Redis / MySQL 8 / httpx / pytest-asyncio / respx。

---

## References

- Ark video API contract: `docs/integrations/volcengine-ark-api.md` §2.1-§2.4
- Current shot draft/render baseline:
  - `backend/app/api/shots.py`
  - `backend/app/domain/services/shot_render_service.py`
  - `backend/app/tasks/ai/render_shot.py`
  - `backend/app/domain/models/shot_render.py`
  - `backend/app/domain/models/storyboard.py`
  - `backend/app/domain/services/aggregate_service.py`
- Celery routing baseline:
  - `backend/app/tasks/celery_app.py`
  - `script/start_celery.sh`

## Scope

**Includes:**

- Keep `POST /api/v1/projects/{project_id}/shots/{shot_id}/render-draft`
- Add `POST /api/v1/projects/{project_id}/shots/{shot_id}/video`
- Add `GET /api/v1/projects/{project_id}/shots/{shot_id}/videos`
- Add `POST /api/v1/projects/{project_id}/shots/{shot_id}/videos/{video_id}/select`
- Keep `POST /api/v1/projects/{project_id}/shots/{shot_id}/lock`, but change lock target from current image render to current video render
- Add video-version persistence model, migration, service, task, and aggregate projection
- Add Ark Seedance create/query client methods
- Add backend tests and `scripts/smoke_m3b.sh` coverage for the new flow

**Excludes:**

- Removing `render-draft`
- AI rewriting of prompt text
- Any prompt suffix/prefix injection
- Batch video generation / parent-child jobs
- Export-task integration and multi-shot stitching
- Audio reference upload or dialogue authoring UI

## Fixed Product Rules

- Final video generation must use the current prompt text **as-is**
- Final video generation must use the current reference images **as-is**
- No AI rewrite, no automatic suffix, no hidden prompt template
- Frontend only exposes:
  - duration
  - resolution
  - model type
- Backend fills fixed defaults for:
  - `ratio` is normalized from `project.ratio` to a provider-supported value, else fallback to `adaptive`
  - `generate_audio = false`
  - `watermark = false`
  - `return_last_frame = true`
  - `execution_expires_after = 3600`
- M3b readiness semantics are video-first:
  - `storyboards.current_video_render_id` becomes the active output pointer for this feature
  - `storyboards.current_render_id` remains legacy/backward-compatible data only
  - stage advancement to `ready_for_export` must rely on final video success/lock semantics, not legacy image-render success

## Proposed API Contract

### `POST /projects/{project_id}/shots/{shot_id}/video`

Request:

```json
{
  "prompt": "镜头标题：乌云压城，雷鸣滚过\n镜头描述：...",
  "references": [
    {
      "id": "scene:01...",
      "kind": "scene",
      "source_id": "01...",
      "name": "东宫闻风声，风雨欲来",
      "image_url": "https://static..."
    }
  ],
  "duration": 5,
  "resolution": "720p",
  "model_type": "fast"
}
```

Response:

```json
{
  "job_id": "01...",
  "sub_job_ids": []
}
```

### `GET /projects/{project_id}/shots/{shot_id}/videos`

Response row:

```json
{
  "id": "01...",
  "shot_id": "01...",
  "version_no": 3,
  "status": "succeeded",
  "prompt_snapshot": {
    "shot": {
      "id": "01...",
      "idx": 1,
      "title": "乌云压城，雷鸣滚过",
      "description": "......",
      "detail": "......",
      "tags": []
    },
    "prompt": "原始提示词",
    "references": []
  },
  "params_snapshot": {
    "duration": 5,
    "resolution": "720p",
    "model_type": "fast",
    "ratio": "9:16",
    "generate_audio": false,
    "watermark": false,
    "return_last_frame": true
  },
  "video_url": "https://static.../v3.mp4",
  "last_frame_url": "https://static.../v3-last-frame.png",
  "provider_task_id": "cgt-2026...",
  "error_code": null,
  "error_msg": null,
  "created_at": "2026-04-23T12:00:00Z",
  "finished_at": "2026-04-23T12:01:05Z",
  "is_current": true
}
```

### Aggregated `GET /projects/{id}`

Required additions:

- `storyboards[*].current_video_render_id`
- `storyboards[*].current_video_url`
- `storyboards[*].current_last_frame_url`
- `storyboards[*].current_video_version_no`
- `storyboards[*].current_video_params_snapshot`
- `generationQueue[*]` for `kind == "render_shot_video"`:
  - `target_id`
  - `shot_id`
  - `video_render_id`
  - `video_url`
  - `last_frame_url`
  - `version_no`
  - `shot_status`
  - `error_code`
  - `error_msg`
  - `params_snapshot`

## File Structure

**Create:**

```text
backend/alembic/versions/<new>_add_shot_video_renders.py
backend/app/domain/models/shot_video_render.py
backend/app/domain/schemas/shot_video.py
backend/app/domain/services/shot_video_service.py
backend/app/tasks/video/__init__.py
backend/app/tasks/video/render_shot_video.py
backend/tests/integration/test_shot_video_api.py
backend/tests/integration/test_render_shot_video_flow.py
backend/tests/unit/test_shot_video_service.py
backend/tests/integration/test_volcano_video_client.py
```

**Modify:**

```text
backend/app/domain/models/storyboard.py
backend/app/domain/models/job.py
backend/app/domain/models/__init__.py
backend/app/domain/schemas/__init__.py
backend/app/domain/services/__init__.py
backend/app/domain/services/aggregate_service.py
backend/app/domain/schemas/project.py
backend/app/api/shots.py
backend/app/main.py
backend/app/tasks/celery_app.py
backend/app/infra/volcano_client.py
backend/app/pipeline/transitions.py
backend/scripts/smoke_m3b.sh
backend/README.md
script/start_celery.sh
```

## Task 1: Add persistent video version model and migration

**Files:**
- Create: `backend/alembic/versions/<new>_add_shot_video_renders.py`
- Create: `backend/app/domain/models/shot_video_render.py`
- Modify: `backend/app/domain/models/storyboard.py`
- Modify: `backend/app/domain/models/job.py`
- Modify: `backend/app/domain/models/__init__.py`

- [ ] **Step 1: Write the failing integration test for the schema shape**

Add to `backend/tests/integration/test_shot_video_api.py`:

```python
@pytest.mark.asyncio
async def test_project_detail_exposes_current_video_render_id(client, db_session):
    from tests.integration.test_shot_render_api import seed_renderable_project

    project, shot = await seed_renderable_project(db_session)
    shot.current_video_render_id = "VID123"
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}")

    assert resp.status_code == 200
    rows = resp.json()["data"]["storyboards"]
    assert rows[0]["current_video_render_id"] == "VID123"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_video_api.py::test_project_detail_exposes_current_video_render_id -q
```

Expected: FAIL because `current_video_render_id` does not exist yet.

- [ ] **Step 3: Add migration and ORM model**

Create `backend/app/domain/models/shot_video_render.py` with:

```python
from datetime import datetime

from sqlalchemy import CHAR, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base
from app.infra.ulid import new_id

SHOT_VIDEO_RENDER_STATUS_VALUES = ["queued", "running", "succeeded", "failed"]


class ShotVideoRender(Base):
    __tablename__ = "shot_video_renders"
    __table_args__ = (
        UniqueConstraint("shot_id", "version_no", name="uq_shot_video_renders_shot_version"),
        Index("ix_shot_video_renders_shot_id", "shot_id"),
        Index("ix_shot_video_renders_provider_task_id", "provider_task_id"),
    )

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    shot_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*SHOT_VIDEO_RENDER_STATUS_VALUES, name="shot_video_render_status"),
        nullable=False,
        default="queued",
    )
    prompt_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    params_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_frame_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    provider_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

Modify `backend/app/domain/models/storyboard.py`:

```python
current_video_render_id: Mapped[str | None] = mapped_column(CHAR(26), nullable=True)
```

Modify `backend/app/domain/models/job.py`:

```python
JOB_KIND_VALUES = [
    # ...
    "render_shot_video",
    "render_batch",
    "export_video",
]
```

- [ ] **Step 4: Add Alembic migration**

Migration must:

- add enum value `render_shot_video` to `jobs.kind`
- add nullable `storyboards.current_video_render_id`
- create table `shot_video_renders`
- include a real `downgrade()` path that removes the FK/column/table in reverse order

Use the same enum-alter pattern already used in:

```text
backend/alembic/versions/1b4e5fd2c7a9_add_extract_characters_job_kind.py
```

- [ ] **Step 5: Run migration-backed test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_video_api.py::test_project_detail_exposes_current_video_render_id -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions backend/app/domain/models
git commit -m "feat(backend): add shot video render persistence"
```

## Task 2: Add Ark Seedance client methods

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/infra/volcano_client.py`
- Create: `backend/tests/integration/test_volcano_video_client.py`

- [ ] **Step 1: Write failing provider client test**

Create `backend/tests/integration/test_volcano_video_client.py`:

```python
import json
import pytest
import httpx

from app.infra.volcano_client import RealVolcanoClient


@pytest.mark.asyncio
async def test_video_task_create_uses_raw_prompt_and_reference_images(patched_settings, respx_mock):
    route = respx_mock.post(url__regex=r".*/contents/generations/tasks").mock(
        return_value=httpx.Response(200, json={"id": "cgt-test"})
    )
    client = RealVolcanoClient()

    await client.video_generations_create(
        model="doubao-seedance-2-0-fast-<exact-endpoint-or-model-id>",
        prompt="原样提示词",
        references=["https://example.com/1.png", "https://example.com/2.png"],
        duration=5,
        resolution="720p",
        ratio="9:16",
    )

    body = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert body["content"][0] == {"type": "text", "text": "原样提示词"}
    assert body["content"][1]["role"] == "reference_image"
    assert body["content"][2]["role"] == "reference_image"
    assert body["duration"] == 5
    assert body["resolution"] == "720p"
    assert body["ratio"] == "9:16"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_volcano_video_client.py::test_video_task_create_uses_raw_prompt_and_reference_images -q
```

Expected: FAIL because `video_generations_create` does not exist.

- [ ] **Step 3: Add config defaults**

Modify `backend/app/config.py`:

```python
ark_video_model_standard: str = "doubao-seedance-2-0-260128"
ark_video_model_fast: str = "doubao-seedance-2-0-fast-<account-specific-suffix-or-endpoint-id>"
ark_video_default_duration: int = 5
ark_video_default_resolution: str = "720p"
ark_video_generate_audio: bool = False
ark_video_watermark: bool = False
ark_video_return_last_frame: bool = True
ark_video_execution_expires_after: int = 3600
```

- [ ] **Step 4: Implement Seedance client methods**

Add to `backend/app/infra/volcano_client.py`:

```python
    async def video_generations_create(
        self,
        *,
        model: str,
        prompt: str,
        references: list[str],
        duration: int,
        resolution: str,
        ratio: str,
        generate_audio: bool = False,
        watermark: bool = False,
        return_last_frame: bool = True,
        execution_expires_after: int = 3600,
    ) -> dict:
        content = [{"type": "text", "text": prompt}]
        for url in references:
            content.append(
                {"type": "image_url", "role": "reference_image", "image_url": {"url": url}}
            )
        body = {
            "model": model,
            "content": content,
            "duration": duration,
            "resolution": resolution,
            "ratio": ratio,
            "generate_audio": generate_audio,
            "watermark": watermark,
            "return_last_frame": return_last_frame,
            "execution_expires_after": execution_expires_after,
        }
        return await self._request_with_retry("POST", "/contents/generations/tasks", body)

    async def video_generations_get(self, task_id: str) -> dict:
        return await self._request_with_retry("GET", f"/contents/generations/tasks/{task_id}", None)
```

Also update `_request_with_retry` so its signature accepts `json_body: dict | None = None`; current implementation does not yet support `None` for GET.

- [ ] **Step 5: Run the provider test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_volcano_video_client.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/infra/volcano_client.py backend/tests/integration/test_volcano_video_client.py
git commit -m "feat(backend): add volcano shot video client"
```

## Task 3: Add shot video service and API contract

**Files:**
- Create: `backend/app/domain/schemas/shot_video.py`
- Create: `backend/app/domain/services/shot_video_service.py`
- Modify: `backend/app/domain/schemas/__init__.py`
- Modify: `backend/app/domain/services/__init__.py`
- Modify: `backend/app/api/shots.py`
- Create: `backend/tests/unit/test_shot_video_service.py`
- Create: `backend/tests/integration/test_shot_video_api.py`

- [ ] **Step 1: Write failing service test**

Add `backend/tests/unit/test_shot_video_service.py`:

```python
import pytest

from tests.integration.test_shot_render_api import seed_renderable_project
from app.domain.services.shot_video_service import ShotVideoService


@pytest.mark.asyncio
async def test_create_video_version_uses_raw_prompt_and_selected_params(db_session):
    project, shot = await seed_renderable_project(db_session)
    svc = ShotVideoService(db_session)

    video = await svc.create_video_version(
        project.id,
        shot.id,
        prompt="原样提示词",
        references=[{
            "id": "scene:1",
            "kind": "scene",
            "source_id": "scene01",
            "name": "东宫",
            "image_url": "https://example.com/scene.png",
        }],
        duration=5,
        resolution="720p",
        model_type="fast",
    )

    assert video.version_no == 1
    assert video.prompt_snapshot["prompt"] == "原样提示词"
    assert video.prompt_snapshot["references"][0]["image_url"] == "https://example.com/scene.png"
    assert video.params_snapshot["duration"] == 5
    assert video.params_snapshot["resolution"] == "720p"
    assert video.params_snapshot["model_type"] == "fast"
```

- [ ] **Step 2: Run the failing service test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_shot_video_service.py::test_create_video_version_uses_raw_prompt_and_selected_params -q
```

Expected: FAIL because service does not exist.

- [ ] **Step 3: Implement request/response schemas**

Create `backend/app/domain/schemas/shot_video.py`:

```python
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.schemas.shot_render import RenderSubmitReference


class ShotVideoSubmitRequest(BaseModel):
    prompt: str = Field(min_length=1)
    references: list[RenderSubmitReference] = Field(min_length=1)
    duration: int = Field(ge=4, le=15)
    resolution: Literal["480p", "720p"]
    model_type: Literal["standard", "fast"]


class ShotVideoVersionRead(BaseModel):
    id: str
    shot_id: str
    version_no: int
    status: str
    prompt_snapshot: dict[str, Any] | None = None
    params_snapshot: dict[str, Any] | None = None
    video_url: str | None = None
    last_frame_url: str | None = None
    provider_task_id: str | None = None
    error_code: str | None = None
    error_msg: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    is_current: bool = False
```

- [ ] **Step 4: Implement service**

`backend/app/domain/services/shot_video_service.py` must:

- validate project stage in `{"characters_locked", "scenes_locked", "rendering", "ready_for_export"}`
- require non-empty prompt and references
- accept frontend presets `{4, 5, 8, 10}`, but validate backend range as `4 <= duration <= 15`
- require `resolution in {"480p", "720p"}`
- require `model_type in {"standard", "fast"}`
- normalize `ratio` from `project.ratio` to an Ark-supported enum and fallback to `"adaptive"` when unknown
- create version row with rich `prompt_snapshot` and explicit `params_snapshot`
- preserve reference order
- keep structured references in `prompt_snapshot["references"]`, and only map to `list[str]` at the Volcano client boundary
- call `advance_to_rendering(project)` when the first final-video submission starts from an earlier renderable stage
- transition the storyboard shot into generating status so aggregate/project stage semantics remain aligned with the existing pipeline
- support:
  - `create_video_version(...)`
  - `list_videos(project_id, shot_id)`
  - `select_video(project_id, shot_id, video_id)`
  - `lock_shot(project_id, shot_id)` based on `current_video_render_id`
- define stage gates explicitly:
  - `select_video(...)` is allowed in all renderable stages
  - `lock_shot(...)` remains limited to `{"rendering", "ready_for_export"}`
  - locking and readiness checks must use the video pointer/status, not `current_render_id`

For model resolution:

```python
def resolve_video_model(settings, model_type: str) -> str:
    return (
        settings.ark_video_model_fast
        if model_type == "fast"
        else settings.ark_video_model_standard
    )
```

- [ ] **Step 5: Implement API routes**

Modify `backend/app/api/shots.py`:

- keep existing `render-draft`
- remove `POST /render` image-generation entry from the active UI path
- add:

```python
@router.post("/{shot_id}/video")
async def generate_video(...):
    ...

@router.get("/{shot_id}/videos")
async def list_videos(...):
    ...

@router.post("/{shot_id}/videos/{video_id}/select")
async def select_video(...):
    ...
```

Ack creation pattern must match existing jobs:

```python
job = await JobService(db).create_job(
    project_id=project_id,
    kind="render_shot_video",
    target_type="shot",
    target_id=shot_id,
    payload={"shot_id": shot_id, "video_render_id": video.id},
)
```

The API/service boundary must stay explicit:

- request schema carries structured `RenderSubmitReference`
- service persists the same structured references in `prompt_snapshot`
- worker/client submit path maps `references -> [ref.image_url for ref in references]`

- [ ] **Step 6: Add API integration test**

Add to `backend/tests/integration/test_shot_video_api.py`:

```python
@pytest.mark.asyncio
async def test_post_video_returns_job_ack(client, db_session, monkeypatch, settings):
    project, shot = await seed_renderable_project(db_session)
    project.stage = "rendering"
    await db_session.commit()

    class FakeTask:
        id = "celery-video-1"

    monkeypatch.setattr("app.api.shots.render_shot_video_task.delay", lambda *args: FakeTask())

    resp = await client.post(
        f"/api/v1/projects/{project.id}/shots/{shot.id}/video",
        json={
            "prompt": "原样提示词",
            "references": [{
                "id": "scene:1",
                "kind": "scene",
                "source_id": "scene01",
                "name": "东宫",
                "image_url": "https://example.com/scene.png",
            }],
            "duration": 5,
            "resolution": "720p",
            "model_type": "fast",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["job_id"]
```

- [ ] **Step 7: Run service + API tests**

Run:

```bash
cd backend
./.venv/bin/pytest \
  tests/unit/test_shot_video_service.py \
  tests/integration/test_shot_video_api.py \
  -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/domain/schemas backend/app/domain/services backend/app/api/shots.py backend/tests/unit/test_shot_video_service.py backend/tests/integration/test_shot_video_api.py
git commit -m "feat(backend): add shot final video api"
```

## Task 4: Add Celery video worker flow and provider polling

**Files:**
- Create: `backend/app/tasks/video/__init__.py`
- Create: `backend/app/tasks/video/render_shot_video.py`
- Modify: `backend/app/tasks/celery_app.py`
- Modify: `backend/app/pipeline/transitions.py`
- Create: `backend/tests/integration/test_render_shot_video_flow.py`

Reuse the existing `seed_renderable_project` helper from `tests/integration/test_shot_render_api.py`; do not invent a second fixture for the same stage setup.

- [ ] **Step 1: Write failing task flow test**

Create `backend/tests/integration/test_render_shot_video_flow.py`:

```python
@pytest.mark.asyncio
async def test_render_shot_video_task_persists_video_and_last_frame(client, db_session, monkeypatch):
    project, shot = await seed_renderable_project(db_session)
    svc = ShotVideoService(db_session)
    video = await svc.create_video_version(
        project.id,
        shot.id,
        prompt="原样提示词",
        references=[{
            "id": "scene:1",
            "kind": "scene",
            "source_id": "scene01",
            "name": "东宫",
            "image_url": "https://example.com/scene.png",
        }],
        duration=5,
        resolution="720p",
        model_type="fast",
    )
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot_video",
        target_type="shot",
        target_id=shot.id,
        payload={"shot_id": shot.id, "video_render_id": video.id},
    )
    await db_session.commit()

    class FakeClient:
        async def video_generations_create(self, **kwargs):
            return {"id": "cgt-123"}

        async def video_generations_get(self, task_id):
            return {
                "id": task_id,
                "status": "succeeded",
                "content": {
                    "video_url": "https://example.com/final.mp4",
                    "last_frame_url": "https://example.com/final.png",
                },
            }

    async def fake_persist_generated_asset(*, url, project_id, kind, ext):
        suffix = "mp4" if ext == "mp4" else "png"
        return f"projects/{project_id}/{kind}/20260423/out.{suffix}"

    monkeypatch.setattr("app.tasks.video.render_shot_video.get_volcano_client", lambda: FakeClient())
    monkeypatch.setattr("app.tasks.video.render_shot_video.persist_generated_asset", fake_persist_generated_asset)

    await _render_shot_video_task(shot.id, video.id, job.id)

    async with get_session_factory()() as session:
        saved = await session.get(ShotVideoRender, video.id)
        saved_shot = await session.get(StoryboardShot, shot.id)
        saved_job = await session.get(Job, job.id)
        assert saved.status == "succeeded"
        assert saved.video_url.endswith(".mp4")
        assert saved.last_frame_url.endswith(".png")
        assert saved_shot.current_video_render_id == video.id
        assert saved_job.status == "succeeded"
```

- [ ] **Step 2: Run the failing task test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_render_shot_video_flow.py::test_render_shot_video_task_persists_video_and_last_frame -q
```

Expected: FAIL because task module does not exist.

- [ ] **Step 3: Implement task module**

Create `backend/app/tasks/video/render_shot_video.py` with the same session lifecycle as `tasks/ai/render_shot.py`, but with:

- `mark_shot_video_running`
- create provider task
- save `provider_task_id`
- poll `video_generations_get(task_id)` every 5 seconds until terminal status or until a deadline derived from `execution_expires_after`
- call `update_job_progress(...)` inside the polling loop so the frontend does not stay at `progress=0`
- persist mp4 and last frame png
- update `job.result = {"shot_id": ..., "video_render_id": ..., "video_url": ...}`

Polling loop skeleton:

```python
deadline = monotonic() + settings.ark_video_execution_expires_after
attempt = 0
while monotonic() < deadline:
    attempt += 1
    provider = await client.video_generations_get(task_id)
    status = provider["status"]
    if status == "succeeded":
        ...
        break
    if status in {"failed", "expired", "cancelled"}:
        ...
        break
    await update_job_progress(session, job, done=min(attempt, 95), total=100, status="running")
    await asyncio.sleep(5)
else:
    ...
```

- [ ] **Step 4: Register `video` task package**

Modify `backend/app/tasks/celery_app.py`:

```python
include=["app.tasks.ai", "app.tasks.video"]
```

Create `backend/app/tasks/video/__init__.py`:

```python
from .render_shot_video import render_shot_video_task

__all__ = ["render_shot_video_task"]
```

Do not leave task routing ambiguous. Choose one concrete contract and keep docs/tests/scripts aligned:

- task decorator name: `video.render_shot_video`
- route by either existing `task_routes["video.*"]` or explicit `queue="video"` on the task decorator
- smoke/tests should assert this exact task name

- [ ] **Step 5: Add transition helpers**

In `backend/app/pipeline/transitions.py`, add helpers symmetrical to image render flow:

- `mark_shot_video_running(video_render)`
- `mark_shot_video_succeeded(shot, video_render, *, video_url, last_frame_url)`
- `mark_shot_video_failed(shot, video_render, *, error_code, error_msg)`
- `select_shot_video_version(shot, video_render)`

They must update `shot.current_video_render_id`, and M3b readiness helpers must key off video success/lock semantics for final output.

- [ ] **Step 6: Run task flow tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_render_shot_video_flow.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/tasks backend/app/pipeline/transitions.py backend/tests/integration/test_render_shot_video_flow.py
git commit -m "feat(backend): add shot video worker flow"
```

## Task 5: Extend aggregate detail and smoke coverage

**Files:**
- Modify: `backend/app/domain/services/aggregate_service.py`
- Modify: `backend/app/domain/schemas/project.py` (if needed)
- Modify: `backend/scripts/smoke_m3b.sh`
- Modify: `backend/README.md`
- Modify: `script/start_celery.sh`

- [ ] **Step 1: Write failing aggregate test**

Add to `backend/tests/integration/test_shot_video_api.py`:

```python
@pytest.mark.asyncio
async def test_project_detail_includes_video_generation_queue_fields(client, db_session):
    project, shot = await seed_renderable_project(db_session)
    video = ShotVideoRender(
        id=new_id(),
        shot_id=shot.id,
        version_no=1,
        status="succeeded",
        params_snapshot={"duration": 5, "resolution": "720p", "model_type": "fast"},
        video_url="projects/p/shot-video/v1.mp4",
        last_frame_url="projects/p/shot-video/v1.png",
    )
    db_session.add(video)
    await db_session.flush()
    job = await JobService(db_session).create_job(
        project_id=project.id,
        kind="render_shot_video",
        target_type="shot",
        target_id=shot.id,
        payload={"shot_id": shot.id, "video_render_id": video.id},
    )
    job.status = "succeeded"
    job.result = {"shot_id": shot.id, "video_render_id": video.id, "video_url": video.video_url}
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}")
    storyboard = next(item for item in resp.json()["data"]["storyboards"] if item["id"] == shot.id)
    row = next(item for item in resp.json()["data"]["generationQueue"] if item["id"] == job.id)
    assert storyboard["current_video_render_id"] == video.id
    assert storyboard["current_video_url"].endswith(".mp4")
    assert row["video_render_id"] == video.id
    assert row["video_url"].endswith(".mp4")
    assert row["last_frame_url"].endswith(".png")
    assert row["params_snapshot"]["duration"] == 5
```

- [ ] **Step 2: Run the failing aggregate test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_video_api.py::test_project_detail_includes_video_generation_queue_fields -q
```

Expected: FAIL because aggregate does not project video fields yet.

- [ ] **Step 3: Extend aggregate projection**

Update `backend/app/domain/services/aggregate_service.py` so it:

- loads `ShotVideoRender` rows for:
  - all `storyboards.current_video_render_id`
  - all `render_shot_video` jobs in queue
- appends to `storyboards[]`:

```python
"current_video_render_id": s.current_video_render_id,
"current_video_url": build_asset_url(video_map[s.current_video_render_id].video_url) if ... else None,
"current_last_frame_url": build_asset_url(video_map[s.current_video_render_id].last_frame_url) if ... else None,
"current_video_version_no": video_map[s.current_video_render_id].version_no if ... else None,
"current_video_params_snapshot": video_map[s.current_video_render_id].params_snapshot if ... else None,
```

- appends to `generationQueue[]` for `kind == "render_shot_video"`:

```python
"shot_id": item.get("target_id"),
"video_render_id": resolved_video_id,
"video_url": build_asset_url(video_map[resolved_video_id].video_url) if ... else None,
"last_frame_url": build_asset_url(video_map[resolved_video_id].last_frame_url) if ... else None,
"version_no": video_map[resolved_video_id].version_no if ... else None,
"params_snapshot": video_map[resolved_video_id].params_snapshot if ... else None,
```

- continue exposing queue rows for active/terminal jobs, but do not rely on queue rows as the only source of current playable video URLs after page reload

- [ ] **Step 4: Update smoke and ops docs**

Modify `backend/scripts/smoke_m3b.sh` to:

- request `render-draft`
- submit `POST /video`
- poll `GET /jobs/{job_id}` until terminal
- assert `GET /shots/{shot_id}/videos` returns at least 1 version
- assert `GET /projects/{project_id}` exposes a playable `storyboards[*].current_video_url`
- verify the persisted asset path ends with `.mp4`

Update `script/start_celery.sh` to note that `video` queue now serves shot-final-video jobs as well as future export tasks.

Update `backend/README.md`:

- add the new endpoints
- add `render_shot_video` to the job-kind description
- explain that M3b final output is per-shot video, not per-shot image
- document that the frontend only exposes duration/resolution/model presets, while the backend validates provider-supported ranges and normalizes ratio

- [ ] **Step 5: Run focused verification**

Run:

```bash
cd backend
./.venv/bin/pytest \
  tests/integration/test_shot_video_api.py \
  tests/integration/test_render_shot_video_flow.py \
  tests/integration/test_volcano_video_client.py \
  -q
```

Then, with local services running:

```bash
cd backend
./scripts/smoke_m3b.sh <PROJECT_ID> <SHOT_ID>
```

Expected:

- pytest PASS
- smoke script exits 0

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/services/aggregate_service.py backend/scripts/smoke_m3b.sh backend/README.md script/start_celery.sh
git commit -m "feat(backend): expose shot final video aggregate state"
```

## Self-Review Checklist

- This plan preserves `render-draft`
- This plan replaces final image generation with final video generation
- This plan enforces raw prompt passthrough
- This plan keeps only duration/resolution/model_type user-configurable
- This plan moves long-running execution onto the `video` queue
- This plan gives frontend enough data to render:
  - generate-video button state
  - video history list
  - current playable video
  - lock-final-version state

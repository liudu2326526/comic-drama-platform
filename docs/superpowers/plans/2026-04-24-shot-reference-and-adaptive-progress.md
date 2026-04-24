# Shot Reference Binding and Adaptive Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the M3b+ shot generation enhancement where users can add, order, and `@`-bind reference images to a shot prompt, while job progress displays an adaptive estimate based on recent successful task durations.

**Architecture:** The backend owns persistent reference candidates, uploaded manual reference assets, prompt/reference snapshots, and adaptive progress estimation. The frontend owns the editing experience: horizontal reference thumbnails, add-reference picker, textarea `@` menu, local draft updates, and rendering the backend-provided `display_progress`. Existing project stage transitions stay unchanged; all job state writes still go through `update_job_progress`.

**Tech Stack:** Backend: Python 3.12 / FastAPI / SQLAlchemy async / Alembic / Celery / MySQL / pytest. Frontend: Vue 3 / TypeScript / Pinia / Axios / Vitest / @vue/test-utils. Commands must use `backend/.venv/bin/<tool>` for backend and `npm` scripts from `frontend/`.

---

## References

- Product spec: `docs/superpowers/specs/2026-04-24-shot-reference-and-adaptive-progress-product-design.md`
- Existing M3b frontend plan: `docs/superpowers/plans/2026-04-22-frontend-m3b-shot-rendering.md`
- Existing M3b backend plan: `docs/superpowers/plans/2026-04-22-backend-m3b-render-shot.md`
- Backend files:
  - `backend/app/api/shots.py`
  - `backend/app/api/jobs.py`
  - `backend/app/config.py`
  - `backend/app/domain/schemas/shot_render.py`
  - `backend/app/domain/schemas/shot_video.py`
  - `backend/app/domain/schemas/job.py`
  - `backend/app/domain/services/reference_candidates.py`
  - `backend/app/domain/services/shot_draft_service.py`
  - `backend/app/domain/services/shot_video_service.py`
  - `backend/app/domain/services/job_service.py`
  - `backend/app/domain/models/shot_draft.py`
  - `backend/app/domain/models/job.py`
  - `backend/app/tasks/video/render_shot_video.py`
- Frontend files:
  - `frontend/src/components/generation/GenerationPanel.vue`
  - `frontend/src/store/workbench.ts`
  - `frontend/src/api/shots.ts`
  - `frontend/src/api/jobs.ts`
  - `frontend/src/composables/useJobPolling.ts`
  - `frontend/src/types/api.ts`
  - `frontend/tests/unit/generation.panel.spec.ts`
  - `frontend/tests/unit/workbench.m3b.store.spec.ts`
  - `frontend/tests/unit/shots.api.spec.ts`
  - `frontend/tests/unit/useJobPolling.spec.ts`

## Scope

**Includes:**

- Backend reference candidate endpoint for a selected shot.
- Backend manual reference registration endpoint backed by a persisted project reference asset row; arbitrary external URLs are rejected.
- Backend history-reference candidates from successful shot image/video versions in the same project.
- Extended reference DTOs with `alias`, `mention_key`, `origin`, and optional `reason`.
- Extended render/video submit payloads with optional `reference_mentions`.
- Prompt snapshot persistence for `reference_mentions` and binding text.
- Adaptive progress fields on job reads: `display_progress`, elapsed seconds, estimated total/remaining seconds, and source label.
- Frontend reference thumbnail rail above the prompt textarea.
- Frontend add-reference picker with search/filter and project-asset registration flow.
- Frontend textarea `@` dropdown sourced from selected references.
- Frontend progress display using backend-provided adaptive progress fields.
- Unit/integration tests for backend DTOs, endpoints, progress estimator, store behavior, and generation panel behavior.

**Excludes:**

- Full rich text editor or immutable inline chips.
- Cross-project reference library.
- Batch render orchestration.
- Provider retry policy changes.
- New project stages or direct mutation of `project.stage`.
- Multipart binary upload UI. This plan only registers URLs/object keys that already belong to the current project asset domain. Arbitrary external image URLs are out of scope because they bypass asset storage and content-safety expectations.

## File Structure

**Create:**

```text
backend/app/domain/schemas/reference.py
backend/app/domain/models/project_reference_asset.py
backend/app/domain/services/job_progress_estimator.py
backend/app/domain/services/shot_reference_service.py
backend/alembic/versions/20260424_add_project_reference_assets.py
backend/tests/unit/test_reference_schema.py
backend/tests/unit/test_job_progress_estimator.py
backend/tests/integration/test_shot_reference_api.py
frontend/src/components/generation/ReferencePickerModal.vue
frontend/src/components/generation/ReferenceMentionMenu.vue
frontend/tests/unit/reference.mention.spec.ts
```

**Modify:**

```text
backend/app/api/jobs.py
backend/app/api/shots.py
backend/app/config.py
backend/app/domain/models/__init__.py
backend/app/domain/schemas/__init__.py
backend/app/domain/schemas/job.py
backend/app/domain/schemas/shot_render.py
backend/app/domain/schemas/shot_video.py
backend/app/domain/services/reference_candidates.py
backend/app/domain/services/shot_draft_service.py
backend/app/domain/services/shot_render_service.py
backend/app/domain/services/shot_video_service.py
backend/app/infra/obs_store.py
backend/app/pipeline/transitions.py
backend/app/tasks/ai/render_shot.py
backend/app/tasks/video/render_shot_video.py
frontend/src/api/shots.ts
frontend/src/api/jobs.ts
frontend/src/components/generation/GenerationPanel.vue
frontend/src/composables/useJobPolling.ts
frontend/src/store/workbench.ts
frontend/src/types/api.ts
frontend/tests/unit/generation.panel.spec.ts
frontend/tests/unit/shots.api.spec.ts
frontend/tests/unit/useJobPolling.spec.ts
frontend/tests/unit/workbench.m3b.store.spec.ts
frontend/README.md
```

## Implementation Order

1. Backend DTOs and candidate endpoints.
2. Backend submit snapshot and prompt binding.
3. Backend adaptive progress estimator.
4. Frontend types, API client, and store state.
5. Frontend picker, thumbnail rail, and `@` mention menu.
6. Frontend adaptive progress UI.
7. Smoke/docs verification.

## Task 1: Backend Reference DTOs and Candidate Endpoint

**Files:**
- Create: `backend/app/domain/schemas/reference.py`
- Modify: `backend/app/domain/schemas/__init__.py`
- Modify: `backend/app/domain/services/reference_candidates.py`
- Modify: `backend/app/domain/services/shot_reference_service.py`
- Modify: `backend/app/api/shots.py`
- Test: `backend/tests/unit/test_reference_schema.py`
- Test: `backend/tests/integration/test_shot_reference_api.py`

- [ ] **Step 1: Write reference schema tests**

Create `backend/tests/unit/test_reference_schema.py`:

```python
from app.domain.schemas.reference import ReferenceCandidateRead, ReferenceOrigin


def test_reference_candidate_accepts_extended_metadata():
    item = ReferenceCandidateRead(
        id="scene:scene01",
        kind="scene",
        source_id="scene01",
        name="长安殿",
        alias="长安殿",
        mention_key="scene:scene01",
        image_url="https://static.example.com/scene.png",
        origin=ReferenceOrigin.AUTO,
        reason="镜头已绑定该场景",
    )

    assert item.alias == "长安殿"
    assert item.mention_key == "scene:scene01"
    assert item.origin == "auto"
```

- [ ] **Step 2: Run the schema test and confirm it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_reference_schema.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'app.domain.schemas.reference'`.

- [ ] **Step 3: Add reference schemas**

Create `backend/app/domain/schemas/reference.py`:

```python
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ReferenceOrigin(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
    HISTORY = "history"


class ReferenceCandidateRead(BaseModel):
    id: str
    kind: str
    source_id: str
    name: str
    alias: str
    mention_key: str
    image_url: str
    origin: ReferenceOrigin = ReferenceOrigin.AUTO
    reason: str | None = None


class ReferenceAssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    image_url: str = Field(min_length=1)
    kind: Literal["manual"] = "manual"


class ReferenceMention(BaseModel):
    mention_key: str
    label: str
```

Modify `backend/app/domain/schemas/__init__.py` to export:

```python
from .reference import ReferenceAssetCreate, ReferenceCandidateRead, ReferenceMention, ReferenceOrigin
```

and add those names to `__all__`.

- [ ] **Step 4: Run the schema test and confirm it passes**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_reference_schema.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Write candidate endpoint integration test**

Append to `backend/tests/integration/test_shot_reference_api.py`:

```python
import pytest

from app.domain.models import Character, Project, Scene, ShotRender, ShotVideoRender, StoryboardShot
from app.pipeline.states import ProjectStageRaw
from app.utils.ulid import new_id


@pytest.mark.asyncio
async def test_list_reference_candidates_returns_extended_fields(client, db_session):
    project = Project(id=new_id(), name="候选图项目", story="正文", stage=ProjectStageRaw.SCENES_LOCKED.value)
    shot = StoryboardShot(
        id=new_id(),
        project_id=project.id,
        idx=1,
        title="秦昭进入长安殿",
        description="秦昭走进长安殿",
        detail="广角镜头",
    )
    scene = Scene(
        id=new_id(),
        project_id=project.id,
        name="长安殿",
        reference_image_url="https://example.com/scene.png",
        status="locked",
    )
    character = Character(
        id=new_id(),
        project_id=project.id,
        name="秦昭",
        reference_image_url="https://example.com/char.png",
        status="locked",
    )
    db_session.add_all([project, shot, scene, character])
    await db_session.commit()

    response = await client.get(f"/api/v1/projects/{project.id}/shots/{shot.id}/reference-candidates")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data
    assert {"id", "alias", "mention_key", "origin", "image_url"} <= set(data[0])
    assert {item["mention_key"] for item in data} >= {f"scene:{scene.id}", f"character:{character.id}"}
```

Also add a history-candidate test in the same file:

```python
@pytest.mark.asyncio
async def test_list_reference_candidates_includes_successful_history_images(client, db_session):
    project = Project(id=new_id(), name="历史图项目", story="正文", stage=ProjectStageRaw.SCENES_LOCKED.value)
    shot = StoryboardShot(id=new_id(), project_id=project.id, idx=1, title="第一镜", description="旧镜头", detail="近景")
    current = StoryboardShot(id=new_id(), project_id=project.id, idx=2, title="第二镜", description="新镜头", detail="近景")
    render = ShotRender(
        id=new_id(),
        shot_id=shot.id,
        version_no=1,
        status="succeeded",
        image_url="projects/pid/shot/history.png",
    )
    video = ShotVideoRender(
        id=new_id(),
        shot_id=shot.id,
        version_no=1,
        status="succeeded",
        last_frame_url="projects/pid/video/last.png",
    )
    db_session.add_all([project, shot, current, render, video])
    await db_session.commit()

    response = await client.get(f"/api/v1/projects/{project.id}/shots/{current.id}/reference-candidates")

    assert response.status_code == 200
    keys = {item["mention_key"] for item in response.json()["data"]}
    assert f"history:{render.id}" in keys
    assert f"history:{video.id}:last_frame" in keys
```

- [ ] **Step 6: Run the endpoint test and confirm it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_reference_api.py::test_list_reference_candidates_returns_extended_fields -v
```

Expected: fail with `404 Not Found` or missing endpoint.

- [ ] **Step 7: Extend reference candidate builder**

Modify each dict in `backend/app/domain/services/reference_candidates.py` to include extended fields:

```python
"alias": scene.name,
"mention_key": f"scene:{scene.id}",
"origin": "auto",
```

and for characters:

```python
"alias": character.name,
"mention_key": f"character:{character.id}",
"origin": "auto",
```

Keep existing keys unchanged for compatibility.

- [ ] **Step 8: Add shot reference service with auto and history candidates**

Create `backend/app/domain/services/shot_reference_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.domain.models import Character, Project, Scene, ShotRender, ShotVideoRender, StoryboardShot
from app.domain.schemas.reference import ReferenceCandidateRead
from app.domain.services.reference_candidates import build_reference_candidates
from app.infra.asset_store import build_asset_url


class ShotReferenceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _asset_ref(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("http://") or value.startswith("https://") or value.startswith("asset://"):
            return value
        return build_asset_url(value)

    async def list_candidates(self, project_id: str, shot_id: str) -> list[ReferenceCandidateRead]:
        project = await self.session.get(Project, project_id)
        shot = await self.session.get(StoryboardShot, shot_id)
        if project is None or shot is None or shot.project_id != project_id:
            raise ApiError(40401, "项目或分镜不存在", http_status=404)

        scenes = (await self.session.execute(select(Scene).where(Scene.project_id == project_id))).scalars().all()
        characters = (await self.session.execute(select(Character).where(Character.project_id == project_id))).scalars().all()
        auto = [
            ReferenceCandidateRead(**item)
            for item in build_reference_candidates(shot, scenes, characters, self._asset_ref)
        ]

        history: list[ReferenceCandidateRead] = []
        project_shot_ids = select(StoryboardShot.id).where(StoryboardShot.project_id == project_id)
        renders = (
            await self.session.execute(
                select(ShotRender)
                .where(ShotRender.shot_id.in_(project_shot_ids), ShotRender.status == "succeeded", ShotRender.image_url.is_not(None))
                .order_by(ShotRender.finished_at.desc())
                .limit(20)
            )
        ).scalars().all()
        for render in renders:
            history.append(
                ReferenceCandidateRead(
                    id=f"history:{render.id}",
                    kind="history",
                    source_id=render.id,
                    name=f"历史镜头 v{render.version_no}",
                    alias=f"历史镜头{render.version_no}",
                    mention_key=f"history:{render.id}",
                    image_url=self._asset_ref(render.image_url),
                    origin="history",
                    reason="同项目已生成镜头图",
                )
            )

        videos = (
            await self.session.execute(
                select(ShotVideoRender)
                .where(
                    ShotVideoRender.shot_id.in_(project_shot_ids),
                    ShotVideoRender.status == "succeeded",
                    ShotVideoRender.last_frame_url.is_not(None),
                )
                .order_by(ShotVideoRender.finished_at.desc())
                .limit(20)
            )
        ).scalars().all()
        for video in videos:
            history.append(
                ReferenceCandidateRead(
                    id=f"history:{video.id}:last_frame",
                    kind="history",
                    source_id=video.id,
                    name=f"上一镜尾帧 v{video.version_no}",
                    alias=f"尾帧{video.version_no}",
                    mention_key=f"history:{video.id}:last_frame",
                    image_url=self._asset_ref(video.last_frame_url),
                    origin="history",
                    reason="同项目已生成视频尾帧",
                )
            )
        return [*auto, *history]
```

This read path is intentionally not gated by renderability stage because candidates are read-only. Mutating endpoints still enforce their own stage guards.

- [ ] **Step 9: Add the candidate endpoint**

Modify `backend/app/api/shots.py` imports:

```python
from app.domain.schemas.reference import ReferenceCandidateRead
from app.domain.services.shot_reference_service import ShotReferenceService
```

Add:

```python
@router.get("/{shot_id}/reference-candidates")
async def list_reference_candidates(project_id: str, shot_id: str, db: AsyncSession = Depends(get_db)):
    try:
        rows = await ShotReferenceService(db).list_candidates(project_id, shot_id)
        return ok([item.model_dump() for item in rows])
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403)
```

- [ ] **Step 10: Run candidate tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_reference_schema.py tests/integration/test_shot_reference_api.py::test_list_reference_candidates_returns_extended_fields tests/integration/test_shot_reference_api.py::test_list_reference_candidates_includes_successful_history_images -v
```

Expected: all selected tests pass.

- [ ] **Step 11: Commit**

```bash
git add backend/app/domain/schemas/reference.py backend/app/domain/schemas/__init__.py backend/app/domain/services/reference_candidates.py backend/app/domain/services/shot_reference_service.py backend/app/api/shots.py backend/tests/unit/test_reference_schema.py backend/tests/integration/test_shot_reference_api.py
git commit -m "feat(backend): add shot reference candidates"
```

## Task 2: Backend Manual Reference Registration

**Files:**
- Create: `backend/app/domain/models/project_reference_asset.py`
- Create: `backend/alembic/versions/20260424_add_project_reference_assets.py`
- Modify: `backend/app/domain/services/shot_reference_service.py`
- Modify: `backend/app/api/shots.py`
- Modify: `backend/app/domain/models/__init__.py`
- Modify: `backend/app/infra/obs_store.py`
- Test: `backend/tests/integration/test_shot_reference_api.py`

- [ ] **Step 1: Write manual reference registration test**

Append to `backend/tests/integration/test_shot_reference_api.py`:

```python
@pytest.mark.asyncio
async def test_register_manual_reference_returns_reference_candidate(client, db_session, monkeypatch):
    project = Project(id=new_id(), name="手动参考图项目", story="正文", stage=ProjectStageRaw.SCENES_LOCKED.value)
    shot = StoryboardShot(id=new_id(), project_id=project.id, idx=1, title="夜景", description="夜色", detail="近景")
    db_session.add_all([project, shot])
    await db_session.commit()
    monkeypatch.setattr("app.domain.services.shot_reference_service.object_exists_in_obs", lambda key: True)

    response = await client.post(
        f"/api/v1/projects/{project.id}/shots/{shot.id}/reference-assets",
        json={
            "name": "手动上传氛围图",
            "image_url": f"projects/{project.id}/manual/reference.png",
            "kind": "manual",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["kind"] == "manual"
    assert data["origin"] == "manual"
    assert data["alias"] == "手动上传氛围图"
    assert data["mention_key"].startswith("manual:")

    reread = await client.get(f"/api/v1/projects/{project.id}/shots/{shot.id}/reference-candidates")
    reread_data = reread.json()["data"]
    assert data["mention_key"] in {item["mention_key"] for item in reread_data}


@pytest.mark.asyncio
async def test_register_manual_reference_rejects_external_url(client, db_session):
    project = Project(id=new_id(), name="外链参考图项目", story="正文", stage=ProjectStageRaw.SCENES_LOCKED.value)
    shot = StoryboardShot(id=new_id(), project_id=project.id, idx=1, title="夜景", description="夜色", detail="近景")
    db_session.add_all([project, shot])
    await db_session.commit()

    response = await client.post(
        f"/api/v1/projects/{project.id}/shots/{shot.id}/reference-assets",
        json={"name": "外链", "image_url": "https://example.com/manual.png", "kind": "manual"},
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_reference_api.py::test_register_manual_reference_returns_reference_candidate -v
```

Expected: fail with missing endpoint.

- [ ] **Step 3: Add persisted project reference asset model**

Create `backend/app/domain/models/project_reference_asset.py`:

```python
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models.base import Base
from app.infra.ulid import new_id


class ProjectReferenceAsset(Base):
    __tablename__ = "project_reference_assets"
    __table_args__ = (
        Index("ix_project_reference_assets_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(CHAR(26), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        CHAR(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
```

Modify `backend/app/domain/models/__init__.py`:

```python
from .project_reference_asset import ProjectReferenceAsset
```

and add `"ProjectReferenceAsset"` to `__all__`.

- [ ] **Step 4: Add migration**

Create `backend/alembic/versions/20260424_add_project_reference_assets.py`:

```python
"""add project reference assets

Revision ID: 20260424_ref_assets
Revises: 88f4e19a3f2d
Create Date: 2026-04-24
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_ref_assets"
down_revision = "88f4e19a3f2d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_reference_assets",
        sa.Column("id", sa.CHAR(length=26), nullable=False),
        sa.Column("project_id", sa.CHAR(length=26), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("image_url", sa.String(length=512), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_reference_assets_project_id", "project_reference_assets", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_reference_assets_project_id", table_name="project_reference_assets")
    op.drop_table("project_reference_assets")
```

If the Alembic head has changed before implementation, rebase this migration onto the then-current single head before committing.

- [ ] **Step 5: Add OBS object existence helper**

Modify `backend/app/infra/obs_store.py`:

```python
def object_exists_in_obs(object_key: str) -> bool:
    s = get_settings()
    object_key = object_key.lstrip("/")
    if s.obs_mock:
        return object_key.startswith("projects/")
    if not all([s.obs_ak, s.obs_sk, s.obs_endpoint, s.obs_bucket]):
        raise RuntimeError("OBS 配置不完整")
    client = _get_obs_client()
    try:
        resp = client.getObjectMetadata(s.obs_bucket, object_key)
        return resp.status < 300
    finally:
        client.close()
```

This helper is synchronous to match the existing OBS wrapper. Async services should call it through `asyncio.to_thread`.

- [ ] **Step 6: Extend reference service with project-asset validation and manual candidates**

Modify `backend/app/domain/services/shot_reference_service.py`:

```python
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.config import get_settings
from app.domain.models import Character, Project, ProjectReferenceAsset, Scene, ShotRender, ShotVideoRender, StoryboardShot
from app.domain.schemas.reference import ReferenceAssetCreate, ReferenceCandidateRead
from app.domain.services.reference_candidates import build_reference_candidates
from app.infra.asset_store import build_asset_url
from app.infra.obs_store import object_exists_in_obs


def _project_asset_prefix(project_id: str) -> str:
    return f"projects/{project_id}/"


def parse_project_asset_ref(project_id: str, image_url: str) -> tuple[str, str]:
    value = image_url.strip()
    if not value:
        raise ApiError(40001, "参考图 URL 不能为空", http_status=422)

    prefix = _project_asset_prefix(project_id)
    if value.startswith(prefix):
        return build_asset_url(value), value

    public_base = (get_settings().obs_public_base_url or "").rstrip("/")
    if public_base and value.startswith(f"{public_base}/{prefix}"):
        return value, value.removeprefix(f"{public_base}/")

    raise ApiError(40001, "手动参考图必须是当前项目资产 URL 或对象 key", http_status=422)


class ShotReferenceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _asset_ref(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("http://") or value.startswith("https://") or value.startswith("asset://"):
            return value
        return build_asset_url(value)

    async def list_candidates(self, project_id: str, shot_id: str) -> list[ReferenceCandidateRead]:
        # Keep the auto/history implementation from Task 1, then append manual assets.
        project = await self.session.get(Project, project_id)
        shot = await self.session.get(StoryboardShot, shot_id)
        if project is None or shot is None or shot.project_id != project_id:
            raise ApiError(40401, "项目或分镜不存在", http_status=404)

        scenes = (await self.session.execute(select(Scene).where(Scene.project_id == project_id))).scalars().all()
        characters = (await self.session.execute(select(Character).where(Character.project_id == project_id))).scalars().all()
        auto = [
            ReferenceCandidateRead(**item)
            for item in build_reference_candidates(shot, scenes, characters, self._asset_ref)
        ]
        history = await self.list_history_assets(project_id)
        manual = await self.list_manual_assets(project_id)
        return [*auto, *history, *manual]

    async def create_manual_asset(self, project_id: str, payload: ReferenceAssetCreate) -> ReferenceCandidateRead:
        image_url, object_key = parse_project_asset_ref(project_id, payload.image_url)
        exists = await asyncio.to_thread(object_exists_in_obs, object_key)
        if not exists:
            raise ApiError(40001, "参考图资产不存在或不属于当前项目", http_status=422)
        row = ProjectReferenceAsset(
            project_id=project_id,
            name=payload.name,
            image_url=image_url,
            object_key=object_key,
            source="manual",
        )
        self.session.add(row)
        await self.session.flush()
        return ReferenceCandidateRead(
            id=f"manual:{row.id}",
            kind="manual",
            source_id=row.id,
            name=row.name,
            alias=row.name,
            mention_key=f"manual:{row.id}",
            image_url=row.image_url,
            origin="manual",
            reason="用户登记的项目资产参考图",
        )

    async def list_manual_assets(self, project_id: str) -> list[ReferenceCandidateRead]:
        rows = (
            await self.session.execute(
                select(ProjectReferenceAsset)
                .where(ProjectReferenceAsset.project_id == project_id)
                .order_by(ProjectReferenceAsset.created_at.desc())
            )
        ).scalars().all()
        return [
            ReferenceCandidateRead(
                id=f"manual:{row.id}",
                kind="manual",
                source_id=row.id,
                name=row.name,
                alias=row.name,
                mention_key=f"manual:{row.id}",
                image_url=row.image_url,
                origin="manual",
                reason="用户登记的项目资产参考图",
            )
            for row in rows
        ]
```

Add `list_history_assets(project_id)` by moving the history query block from Task 1 into its own method. Do not replace the class from Task 1 with a partial class; keep the constructor, `_asset_ref`, and `list_candidates` behavior shown here. The final class must contain all of these methods in one class: `__init__`, `_asset_ref`, `list_candidates`, `list_history_assets`, `create_manual_asset`, and `list_manual_assets`.

- [ ] **Step 7: Add endpoint using persisted registration**

Modify `backend/app/api/shots.py` imports:

```python
from app.domain.schemas.reference import ReferenceAssetCreate, ReferenceCandidateRead
from app.domain.services.shot_reference_service import ShotReferenceService
```

Add:

```python
@router.post("/{shot_id}/reference-assets")
async def register_reference_asset(
    project_id: str,
    shot_id: str,
    payload: ReferenceAssetCreate,
    db: AsyncSession = Depends(get_db),
):
    await ShotDraftService(db).ensure_draft_renderable(project_id, shot_id)
    item = await ShotReferenceService(db).create_manual_asset(project_id, payload)
    await db.commit()
    return ok(item.model_dump())
```

`GET /reference-candidates` should continue to call `ShotReferenceService(db).list_candidates(...)`; that method now appends manual assets.

- [ ] **Step 8: Run manual reference tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_reference_api.py -v
```

Expected: both reference API tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/domain/models/project_reference_asset.py backend/alembic/versions/20260424_add_project_reference_assets.py backend/app/domain/models/__init__.py backend/app/domain/services/shot_reference_service.py backend/app/api/shots.py backend/tests/integration/test_shot_reference_api.py
git commit -m "feat(backend): register manual shot references"
```

## Task 3: Backend Submit Payload and Binding Snapshot

**Files:**
- Modify: `backend/app/domain/schemas/shot_video.py`
- Modify: `backend/app/domain/schemas/shot_render.py`
- Modify: `backend/app/domain/services/shot_video_service.py`
- Modify: `backend/app/domain/services/shot_render_service.py`
- Modify: `backend/app/tasks/video/render_shot_video.py`
- Test: `backend/tests/unit/test_schema_validation.py`
- Test: `backend/tests/unit/test_shot_video_service.py`
- Test: `backend/tests/integration/test_render_shot_video_flow.py`

- [ ] **Step 1: Write schema validation test for mentions**

Append to `backend/tests/unit/test_schema_validation.py`:

```python
from app.domain.schemas.shot_video import ShotVideoSubmitRequest


def test_shot_video_submit_accepts_reference_mentions():
    payload = ShotVideoSubmitRequest(
        prompt="远景，@长安殿 内，@秦昭 走入画面",
        references=[
            {
                "id": "scene:scene01",
                "kind": "scene",
                "source_id": "scene01",
                "name": "长安殿",
                "alias": "长安殿",
                "mention_key": "scene:scene01",
                "image_url": "https://example.com/scene.png",
            }
        ],
        reference_mentions=[{"mention_key": "scene:scene01", "label": "长安殿"}],
        resolution="480p",
        model_type="fast",
    )

    assert payload.reference_mentions[0].label == "长安殿"
    assert payload.references[0].mention_key == "scene:scene01"
```

- [ ] **Step 2: Run the schema test and confirm it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_schema_validation.py::test_shot_video_submit_accepts_reference_mentions -v
```

Expected: fail because `alias`, `mention_key`, or `reference_mentions` is not accepted.

- [ ] **Step 3: Extend submit schemas**

Modify `backend/app/domain/schemas/shot_render.py`:

```python
from pydantic import Field

from app.domain.schemas.reference import ReferenceMention


class RenderSubmitReference(BaseModel):
    id: str
    kind: str
    source_id: str
    name: str
    image_url: str
    alias: str | None = None
    mention_key: str | None = None
    origin: str | None = None


class RenderSubmitRequest(BaseModel):
    prompt: str
    references: list[RenderSubmitReference]
    reference_mentions: list[ReferenceMention] = Field(default_factory=list)
```

Modify `backend/app/domain/schemas/shot_video.py` so its request uses the extended `RenderSubmitReference` and adds:

```python
reference_mentions: list[ReferenceMention] = Field(default_factory=list)
```

- [ ] **Step 4: Run schema validation**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_schema_validation.py::test_shot_video_submit_accepts_reference_mentions -v
```

Expected: pass.

- [ ] **Step 5: Write service snapshot test**

Append to `backend/tests/unit/test_shot_video_service.py`:

```python
from app.domain.schemas.reference import ReferenceMention


def test_reference_binding_text_uses_mentions():
    from app.domain.services.shot_video_service import build_reference_binding_text

    text = build_reference_binding_text(
        references=[
            {"id": "scene:scene01", "name": "长安殿", "alias": "长安殿", "mention_key": "scene:scene01", "kind": "scene"},
            {"id": "character:char01", "name": "秦昭", "alias": "秦昭", "mention_key": "character:char01", "kind": "character"},
        ],
        mentions=[
            ReferenceMention(mention_key="scene:scene01", label="长安殿"),
            ReferenceMention(mention_key="character:char01", label="秦昭"),
        ],
    )

    assert "图片1 = @长安殿" in text
    assert "图片2 = @秦昭" in text
```

- [ ] **Step 6: Run service test and confirm it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_shot_video_service.py::test_reference_binding_text_uses_mentions -v
```

Expected: fail with missing `build_reference_binding_text`.

- [ ] **Step 7: Add binding text helper**

Modify `backend/app/domain/services/shot_video_service.py`:

```python
from app.domain.schemas.reference import ReferenceMention


def build_reference_binding_text(references: list[dict], mentions: list[ReferenceMention]) -> str:
    mention_map = {item.mention_key: item.label for item in mentions}
    lines = ["参考图绑定:"]
    for index, ref in enumerate(references, start=1):
        key = str(ref.get("mention_key") or ref.get("id"))
        label = mention_map.get(key) or str(ref.get("alias") or ref.get("name") or key)
        prefix = f"@{label}" if key in mention_map else label
        kind = str(ref.get("kind") or "reference")
        lines.append(f"图片{index} = {prefix},作为{kind}参考。")
    return "\n".join(lines)
```

- [ ] **Step 8: Persist mentions and binding text in image and video snapshots**

In `ShotVideoService.create_video_version`, when building `prompt_snapshot`, include:

```python
"reference_mentions": [item.model_dump() for item in reference_mentions],
"reference_binding_text": build_reference_binding_text(
    [item.model_dump() for item in references],
    reference_mentions,
),
```

Pass `payload.reference_mentions` from `backend/app/api/shots.py` into `create_video_version`. Keep `reference_mentions` optional with default `[]`.

Apply the same snapshot fields in `ShotRenderService.create_render_version` for `POST /render`. Pass `payload.reference_mentions` into the render snapshot and keep old snapshots readable when those keys are missing.

- [ ] **Step 9: Append binding text to image and video provider prompts**

In `backend/app/tasks/video/render_shot_video.py`, before calling `generate_video`, read:

```python
binding_text = str(snapshot.get("reference_binding_text") or "")
prompt = snapshot.get("prompt") or ""
if binding_text:
    prompt = f"{prompt}\n\n{binding_text}"
```

Use this `prompt` in the provider call. Do not mutate `prompt_snapshot`.

Apply the same pattern in `backend/app/tasks/ai/render_shot.py` before calling image generation. Both task paths must use `snapshot.get("reference_binding_text")` so old snapshots without the key remain compatible.

- [ ] **Step 10: Move ready-for-export rollback to a transition helper**

Modify `backend/app/pipeline/transitions.py`:

```python
def return_to_rendering(project: Project) -> None:
    if project.stage != ProjectStageRaw.READY_FOR_EXPORT.value:
        advance_to_rendering(project)
        return
    project.stage = ProjectStageRaw.RENDERING.value
```

Then replace the direct assignment in `ShotVideoService.create_video_version`:

```python
return_to_rendering(project)
```

Do not leave `project.stage = ...` in `backend/app/domain/services/shot_video_service.py`; `pipeline/transitions.py` remains the only stage writer.

- [ ] **Step 11: Run related backend tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_schema_validation.py::test_shot_video_submit_accepts_reference_mentions tests/unit/test_shot_video_service.py tests/integration/test_render_shot_flow.py tests/integration/test_render_shot_video_flow.py -v
```

Expected: all selected tests pass.

- [ ] **Step 12: Commit**

```bash
git add backend/app/domain/schemas/shot_render.py backend/app/domain/schemas/shot_video.py backend/app/domain/services/shot_render_service.py backend/app/domain/services/shot_video_service.py backend/app/pipeline/transitions.py backend/app/api/shots.py backend/app/tasks/ai/render_shot.py backend/app/tasks/video/render_shot_video.py backend/tests/unit/test_schema_validation.py backend/tests/unit/test_shot_video_service.py backend/tests/integration/test_render_shot_flow.py backend/tests/integration/test_render_shot_video_flow.py
git commit -m "feat(backend): persist shot reference bindings"
```

## Task 4: Backend Adaptive Job Progress

**Files:**
- Create: `backend/app/domain/services/job_progress_estimator.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/domain/schemas/job.py`
- Modify: `backend/app/api/jobs.py`
- Test: `backend/tests/unit/test_job_progress_estimator.py`
- Test: `backend/tests/integration/test_jobs_api.py`

- [ ] **Step 1: Write estimator unit tests**

Create `backend/tests/unit/test_job_progress_estimator.py`:

```python
from datetime import datetime, timedelta, timezone

from app.domain.services.job_progress_estimator import estimate_display_progress


def test_estimate_display_progress_uses_recent_p75_and_caps_running_progress():
    now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    result = estimate_display_progress(
        job_progress=20,
        job_status="running",
        created_at=now - timedelta(seconds=60),
        finished_at=None,
        now=now,
        recent_durations=[40, 60, 80, 100],
        default_seconds=120,
        min_seconds=10,
        cap=95,
    )

    assert result.display_progress == 75
    assert result.estimated_total_seconds == 80
    assert result.estimated_source == "recent_4"


def test_estimate_display_progress_falls_back_to_default_seconds():
    now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    result = estimate_display_progress(
        job_progress=10,
        job_status="running",
        created_at=now - timedelta(seconds=30),
        finished_at=None,
        now=now,
        recent_durations=[],
        default_seconds=90,
        min_seconds=10,
        cap=95,
    )

    assert result.display_progress == 33
    assert result.estimated_total_seconds == 90
    assert result.estimated_source == "default"


def test_estimate_display_progress_returns_100_for_success():
    now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    result = estimate_display_progress(
        job_progress=60,
        job_status="succeeded",
        created_at=now - timedelta(seconds=30),
        finished_at=now,
        now=now,
        recent_durations=[],
        default_seconds=90,
        min_seconds=10,
        cap=95,
    )

    assert result.display_progress == 100


def test_estimate_display_progress_freezes_failed_jobs_at_finished_at():
    now = datetime(2026, 4, 24, 12, 5, tzinfo=timezone.utc)
    created = datetime(2026, 4, 24, 12, 0)
    finished = datetime(2026, 4, 24, 12, 1)
    result = estimate_display_progress(
        job_progress=20,
        job_status="failed",
        created_at=created,
        finished_at=finished,
        now=now,
        recent_durations=[],
        default_seconds=120,
        min_seconds=10,
        cap=95,
    )

    assert result.elapsed_seconds == 60
    assert result.display_progress == 50
```

- [ ] **Step 2: Run estimator tests and confirm they fail**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_job_progress_estimator.py -v
```

Expected: fail with missing module.

- [ ] **Step 3: Implement estimator**

Create `backend/app/domain/services/job_progress_estimator.py`:

```python
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ProgressEstimate:
    display_progress: int
    elapsed_seconds: int | None
    estimated_total_seconds: int | None
    estimated_remaining_seconds: int | None
    estimated_source: str


def _p75(values: list[int]) -> int:
    ordered = sorted(v for v in values if v > 0)
    if not ordered:
        return 0
    index = max(0, int((len(ordered) - 1) * 0.75))
    return ordered[index]


def duration_seconds(start: datetime, end: datetime) -> int:
    def aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return max(0, int((aware(end) - aware(start)).total_seconds()))


def estimate_display_progress(
    *,
    job_progress: int,
    job_status: str,
    created_at: datetime | None,
    finished_at: datetime | None,
    now: datetime,
    recent_durations: list[int],
    default_seconds: int,
    min_seconds: int,
    cap: int,
) -> ProgressEstimate:
    if job_status == "succeeded":
        return ProgressEstimate(100, None, None, 0, "terminal")

    if created_at is None:
        return ProgressEstimate(job_progress, None, None, None, "raw")

    end = finished_at if job_status in {"failed", "canceled"} and finished_at is not None else now
    elapsed = duration_seconds(created_at, end)
    recent_total = _p75(recent_durations)
    if recent_total > 0:
        total = max(min_seconds, recent_total)
        source = f"recent_{len(recent_durations)}"
    else:
        total = max(min_seconds, default_seconds)
        source = "default"

    estimated = int(elapsed / total * 100)
    if job_status not in {"failed", "canceled"}:
        display = min(cap, max(job_progress, estimated))
    else:
        display = max(job_progress, min(cap, estimated))
    remaining = max(0, total - elapsed)
    return ProgressEstimate(display, elapsed, total, remaining, source)
```

- [ ] **Step 4: Add config values**

Modify `backend/app/config.py` `Settings`:

```python
job_progress_history_size: int = 20
job_progress_estimate_cap: int = 95
job_progress_estimate_min_seconds: int = 10
job_progress_estimate_default_seconds: int = 90
```

Use existing settings naming style if the file uses uppercase env aliases.

- [ ] **Step 5: Extend job schema**

Modify `backend/app/domain/schemas/job.py`:

```python
display_progress: int | None = None
elapsed_seconds: int | None = None
estimated_total_seconds: int | None = None
estimated_remaining_seconds: int | None = None
estimated_source: str | None = None
```

- [ ] **Step 6: Add recent duration lookup in jobs API**

Modify `backend/app/api/jobs.py` to query recent successful jobs with the same estimate group, not just the same `kind`:

```python
from datetime import datetime, timezone
from sqlalchemy import desc, select
from app.domain.models import Job, ShotVideoRender
from app.domain.services.job_progress_estimator import duration_seconds, estimate_display_progress
from app.config import get_settings
```

Inside `get_job`, after loading the current job:

```python
settings = get_settings()
group_filters = [Job.kind == job.kind, Job.status == "succeeded", Job.finished_at.is_not(None)]
if job.kind == "render_shot_video":
    current_video_id = (job.payload or {}).get("video_render_id")
    current_video = await db.get(ShotVideoRender, current_video_id) if current_video_id else None
    current_params = current_video.params_snapshot if current_video else {}
    group_filters.append(Job.payload["video_render_id"].is_not(None))
    # The Python filter below keeps this portable across MySQL JSON behavior in tests.

recent_jobs = (
    await db.execute(
        select(Job)
        .where(*group_filters)
        .order_by(desc(Job.finished_at))
        .limit(settings.job_progress_history_size * 4)
    )
).scalars().all()
if job.kind == "render_shot_video":
    filtered = []
    for item in recent_jobs:
        video_id = (item.payload or {}).get("video_render_id")
        video = await db.get(ShotVideoRender, video_id) if video_id else None
        params = video.params_snapshot if video else {}
        if {
            "model_type": params.get("model_type"),
            "resolution": params.get("resolution"),
            "duration": params.get("duration"),
        } == {
            "model_type": current_params.get("model_type"),
            "resolution": current_params.get("resolution"),
            "duration": current_params.get("duration"),
        }:
            filtered.append(item)
    recent_jobs = filtered[: settings.job_progress_history_size]
else:
    recent_jobs = recent_jobs[: settings.job_progress_history_size]
recent_durations = [
    duration_seconds(item.created_at, item.finished_at)
    for item in recent_jobs
    if item.created_at and item.finished_at
]
estimate = estimate_display_progress(
    job_progress=job.progress,
    job_status=job.status,
    created_at=job.created_at,
    finished_at=job.finished_at,
    now=datetime.now(timezone.utc),
    recent_durations=recent_durations,
    default_seconds=settings.job_progress_estimate_default_seconds,
    min_seconds=settings.job_progress_estimate_min_seconds,
    cap=settings.job_progress_estimate_cap,
)
```

Include `estimate` fields in the response.

- [ ] **Step 7: Add jobs API integration test**

If `backend/tests/integration/test_jobs_api.py` does not exist, create it. Add:

```python
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.models import Job, Project, ShotVideoRender, StoryboardShot
from app.utils.ulid import new_id


@pytest.mark.asyncio
async def test_get_job_includes_adaptive_progress_fields(client, db_session):
    project = Project(id=new_id(), name="进度项目", story="正文")
    shot = StoryboardShot(id=new_id(), project_id=project.id, idx=1, title="镜头", description="描述", detail="细节")
    now = datetime.now(timezone.utc)
    finished_video = ShotVideoRender(
        id=new_id(),
        shot_id=shot.id,
        version_no=1,
        status="succeeded",
        params_snapshot={"model_type": "fast", "resolution": "480p", "duration": 5},
    )
    running_video = ShotVideoRender(
        id=new_id(),
        shot_id=shot.id,
        version_no=2,
        status="running",
        params_snapshot={"model_type": "fast", "resolution": "480p", "duration": 5},
    )
    finished = Job(
        id=new_id(),
        project_id=project.id,
        kind="render_shot_video",
        status="succeeded",
        progress=100,
        target_type="shot",
        target_id=shot.id,
        payload={"video_render_id": finished_video.id},
        created_at=now - timedelta(seconds=80),
        finished_at=now,
    )
    running = Job(
        id=new_id(),
        project_id=project.id,
        kind="render_shot_video",
        status="running",
        progress=5,
        target_type="shot",
        target_id=shot.id,
        payload={"video_render_id": running_video.id},
        created_at=now - timedelta(seconds=40),
    )
    db_session.add_all([project, shot, finished_video, running_video, finished, running])
    await db_session.commit()

    response = await client.get(f"/api/v1/jobs/{running.id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["display_progress"] >= 5
    assert data["estimated_total_seconds"] is not None
    assert data["estimated_remaining_seconds"] is not None
    assert data["estimated_source"].startswith("recent_")
    assert data["target_id"] == shot.id
```

If the current jobs API response does not include `target_id` / `target_type`, add them to `GET /jobs/{job_id}` in the same task. The frontend progress override relies on `target_id == shot_id` for `render_shot` and `render_shot_video`.

- [ ] **Step 8: Run backend progress tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_job_progress_estimator.py tests/integration/test_jobs_api.py::test_get_job_includes_adaptive_progress_fields -v
```

Expected: all selected tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/domain/services/job_progress_estimator.py backend/app/config.py backend/app/domain/schemas/job.py backend/app/api/jobs.py backend/tests/unit/test_job_progress_estimator.py backend/tests/integration/test_jobs_api.py
git commit -m "feat(backend): add adaptive job progress"
```

## Task 5: Frontend Types, API Client, and Store

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/shots.ts`
- Modify: `frontend/src/store/workbench.ts`
- Test: `frontend/tests/unit/shots.api.spec.ts`
- Test: `frontend/tests/unit/workbench.m3b.store.spec.ts`

- [ ] **Step 1: Extend frontend API types**

Modify `frontend/src/types/api.ts`:

```ts
export type ReferenceOrigin = "auto" | "manual" | "history";

export interface ReferenceCandidateRead {
  id: string;
  kind: string;
  source_id: string;
  name: string;
  alias: string;
  mention_key: string;
  image_url: string;
  origin: ReferenceOrigin;
  reason?: string | null;
}

export interface ReferenceAssetCreate {
  name: string;
  image_url: string;
  kind?: "manual";
}

export interface ReferenceMention {
  mention_key: string;
  label: string;
}
```

Extend `RenderSubmitReference`:

```ts
alias?: string | null;
mention_key?: string | null;
origin?: ReferenceOrigin | string | null;
```

Extend `ShotVideoSubmitRequest`:

```ts
reference_mentions?: ReferenceMention[];
```

Extend `JobState`:

```ts
display_progress?: number | null;
elapsed_seconds?: number | null;
estimated_total_seconds?: number | null;
estimated_remaining_seconds?: number | null;
estimated_source?: string | null;
```

- [ ] **Step 2: Write shots API tests**

Append to `frontend/tests/unit/shots.api.spec.ts`:

```ts
it("listReferenceCandidates -> GET /projects/:id/shots/:sid/reference-candidates", async () => {
  vi.spyOn(client, "get").mockResolvedValueOnce({
    data: {
      code: 0,
      message: "ok",
      data: [{ id: "scene:s1", kind: "scene", source_id: "s1", name: "长安殿", alias: "长安殿", mention_key: "scene:s1", image_url: "https://img", origin: "auto" }]
    }
  });

  const rows = await shotsApi.listReferenceCandidates("pid", "sid");

  expect(client.get).toHaveBeenCalledWith("/projects/pid/shots/sid/reference-candidates");
  expect(rows[0].mention_key).toBe("scene:s1");
});

it("registerReferenceAsset -> POST /projects/:id/shots/:sid/reference-assets", async () => {
  vi.spyOn(client, "post").mockResolvedValueOnce({
    data: {
      code: 0,
      message: "ok",
      data: { id: "manual:m1", kind: "manual", source_id: "m1", name: "手动图", alias: "手动图", mention_key: "manual:m1", image_url: "https://static.example.com/projects/pid/manual/ref.png", origin: "manual" }
    }
  });

  const row = await shotsApi.registerReferenceAsset("pid", "sid", { name: "手动图", image_url: "projects/pid/manual/ref.png" });

  expect(client.post).toHaveBeenCalledWith("/projects/pid/shots/sid/reference-assets", { name: "手动图", image_url: "projects/pid/manual/ref.png" });
  expect(row.origin).toBe("manual");
});
```

- [ ] **Step 3: Run API tests and confirm they fail**

Run:

```bash
cd frontend
npm run test -- shots.api.spec.ts
```

Expected: fail with missing API methods.

- [ ] **Step 4: Add API client methods**

Modify `frontend/src/api/shots.ts`:

```ts
import type { ReferenceAssetCreate, ReferenceCandidateRead } from "@/types/api";

async function listReferenceCandidates(projectId: string, shotId: string): Promise<ReferenceCandidateRead[]> {
  const r = await client.get(`/projects/${projectId}/shots/${shotId}/reference-candidates`);
  return unwrap(r);
}

async function registerReferenceAsset(
  projectId: string,
  shotId: string,
  payload: ReferenceAssetCreate
): Promise<ReferenceCandidateRead> {
  const r = await client.post(`/projects/${projectId}/shots/${shotId}/reference-assets`, payload);
  return unwrap(r);
}
```

Export both methods from `shotsApi`.

- [ ] **Step 5: Run API tests**

Run:

```bash
cd frontend
npm run test -- shots.api.spec.ts
```

Expected: pass.

- [ ] **Step 6: Add store tests**

Append to `frontend/tests/unit/workbench.m3b.store.spec.ts`:

```ts
it("loads and caches reference candidates per shot", async () => {
  const store = useWorkbenchStore();
  store.current = { id: "pid" } as never;
  vi.spyOn(shotsApi, "listReferenceCandidates").mockResolvedValueOnce([
    { id: "scene:s1", kind: "scene", source_id: "s1", name: "长安殿", alias: "长安殿", mention_key: "scene:s1", image_url: "https://img", origin: "auto" }
  ]);

  const rows = await store.fetchReferenceCandidates("sid");

  expect(rows).toHaveLength(1);
  expect(store.referenceCandidatesFor("sid")[0].alias).toBe("长安殿");
});

it("generates video payload with reference mentions", async () => {
  const store = useWorkbenchStore();
  store.current = { id: "pid" } as never;
  store.updateRenderDraft("sid", {
    shot_id: "sid",
    prompt: "@长安殿 内景",
    references: [{ id: "scene:s1", kind: "scene", source_id: "s1", name: "长安殿", alias: "长安殿", mention_key: "scene:s1", image_url: "https://img", origin: "auto", reason: "命中" }]
  } as never);
  vi.spyOn(shotsApi, "generateVideo").mockResolvedValueOnce({ job_id: "job1", sub_job_ids: [] });

  await store.generateVideoFromDraft("sid");

  expect(shotsApi.generateVideo).toHaveBeenCalledWith("pid", "sid", expect.objectContaining({
    reference_mentions: [{ mention_key: "scene:s1", label: "长安殿" }]
  }));
});
```

- [ ] **Step 7: Run store tests and confirm they fail**

Run:

```bash
cd frontend
npm run test -- workbench.m3b.store.spec.ts
```

Expected: fail with missing store methods or payload fields.

- [ ] **Step 8: Add store state and helpers**

Modify `frontend/src/store/workbench.ts`:

```ts
const referenceCandidates = ref<Record<string, ReferenceCandidateRead[]>>({});

function referenceCandidatesFor(shotId: string): ReferenceCandidateRead[] {
  return referenceCandidates.value[shotId] ?? [];
}

async function fetchReferenceCandidates(shotId: string): Promise<ReferenceCandidateRead[]> {
  if (!current.value) throw new Error("fetchReferenceCandidates: no current project");
  const rows = await shotsApi.listReferenceCandidates(current.value.id, shotId);
  referenceCandidates.value[shotId] = rows;
  return rows;
}

async function registerManualReference(shotId: string, payload: ReferenceAssetCreate): Promise<ReferenceCandidateRead> {
  if (!current.value) throw new Error("registerManualReference: no current project");
  const row = await shotsApi.registerReferenceAsset(current.value.id, shotId, payload);
  referenceCandidates.value[shotId] = [row, ...referenceCandidatesFor(shotId)];
  return row;
}

function extractReferenceMentions(prompt: string, refs: RenderSubmitReference[]): ReferenceMention[] {
  return refs
    .filter((ref) => {
      const label = ref.alias ?? ref.name;
      return Boolean(label && prompt.includes(`@${label}`));
    })
    .map((ref) => ({ mention_key: ref.mention_key ?? ref.id, label: ref.alias ?? ref.name }));
}

function withUniqueReferenceAliases<T extends { id: string; name: string; alias?: string | null; kind: string }>(refs: T[]): T[] {
  const counts = refs.reduce<Record<string, number>>((acc, ref) => {
    const key = ref.alias ?? ref.name;
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
  return refs.map((ref) => {
    const base = ref.alias ?? ref.name;
    if (counts[base] <= 1) return { ...ref, alias: base };
    const suffix = ref.kind === "character" ? "角色" : ref.kind === "scene" ? "场景" : ref.kind === "manual" ? "手动图" : "历史图";
    return { ...ref, alias: `${base}-${suffix}` };
  });
}
```

Use `withUniqueReferenceAliases` when adding references to a draft and before extracting mentions, so duplicate names are visible and bindable. In `generateVideoFromDraft`, add:

```ts
reference_mentions: extractReferenceMentions(draft.prompt, draft.references),
```

Return the new methods from the store.

- [ ] **Step 9: Run store tests**

Run:

```bash
cd frontend
npm run test -- workbench.m3b.store.spec.ts
```

Expected: pass.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/api/shots.ts frontend/src/store/workbench.ts frontend/tests/unit/shots.api.spec.ts frontend/tests/unit/workbench.m3b.store.spec.ts
git commit -m "feat(frontend): add shot reference store contract"
```

## Task 6: Frontend Reference Picker and Thumbnail Rail

**Files:**
- Create: `frontend/src/components/generation/ReferencePickerModal.vue`
- Modify: `frontend/src/components/generation/GenerationPanel.vue`
- Test: `frontend/tests/unit/generation.panel.spec.ts`

- [ ] **Step 1: Write generation panel reference UI test**

Append to `frontend/tests/unit/generation.panel.spec.ts`:

```ts
it("renders selected references above prompt and can remove one", async () => {
  const store = useWorkbenchStore();
  store.current = makeProject({ stage_raw: "scenes_locked" });
  store.selectedShotId = "SH1";
  store.updateRenderDraft("SH1", {
    shot_id: "SH1",
    prompt: "镜头提示词",
    references: [
      { id: "scene:s1", kind: "scene", source_id: "s1", name: "长安殿", alias: "长安殿", mention_key: "scene:s1", image_url: "https://img", origin: "auto", reason: "命中" }
    ]
  } as never);

  const wrapper = mount(GenerationPanel, { global: testPlugins() });

  expect(wrapper.get('[data-testid="reference-rail"]').text()).toContain("长安殿");
  await wrapper.get('[data-testid="remove-reference-scene:s1"]').trigger("click");
  expect(store.renderDraftFor("SH1")?.references).toHaveLength(0);
});
```

- [ ] **Step 2: Run panel test and confirm it fails**

Run:

```bash
cd frontend
npm run test -- generation.panel.spec.ts
```

Expected: fail with missing `reference-rail` or remove test id.

- [ ] **Step 3: Create ReferencePickerModal**

Create `frontend/src/components/generation/ReferencePickerModal.vue`:

```vue
<script setup lang="ts">
import { computed, ref } from "vue";
import type { ReferenceCandidateRead } from "@/types/api";

const props = defineProps<{
  open: boolean;
  candidates: ReferenceCandidateRead[];
  selectedIds: string[];
}>();

const emit = defineEmits<{
  close: [];
  add: [items: ReferenceCandidateRead[]];
  register: [payload: { name: string; image_url: string }];
}>();

const query = ref("");
const filter = ref("all");
const checked = ref<Set<string>>(new Set());
const assetName = ref("");
const assetUrl = ref("");

const filtered = computed(() =>
  props.candidates.filter((item) => {
    const matchesType = filter.value === "all" || item.origin === filter.value || item.kind === filter.value;
    const text = `${item.name} ${item.alias} ${item.reason ?? ""}`;
    return matchesType && text.includes(query.value.trim());
  })
);

function toggle(id: string) {
  const next = new Set(checked.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  checked.value = next;
}

function submit() {
  emit("add", props.candidates.filter((item) => checked.value.has(item.id)));
  checked.value = new Set();
}

function submitRegister() {
  if (!assetName.value.trim() || !assetUrl.value.trim()) return;
  emit("register", { name: assetName.value.trim(), image_url: assetUrl.value.trim() });
  assetName.value = "";
  assetUrl.value = "";
}
</script>

<template>
  <div v-if="open" class="reference-modal" role="dialog" aria-modal="true">
    <div class="reference-modal-card">
      <header>
        <strong>添加参考图</strong>
        <button type="button" class="ghost-btn small" @click="emit('close')">关闭</button>
      </header>
      <input v-model="query" class="reference-search" placeholder="搜索参考图" data-testid="reference-search" />
      <div class="selector-row">
        <button v-for="item in ['all', 'scene', 'character', 'history', 'manual']" :key="item" type="button" class="ghost-btn small" :class="{ active: filter === item }" @click="filter = item">{{ item }}</button>
      </div>
      <div class="reference-picker-grid">
        <button v-for="item in filtered" :key="item.id" type="button" class="reference-picker-card" :disabled="selectedIds.includes(item.id)" @click="toggle(item.id)">
          <img :src="item.image_url" :alt="item.name" />
          <strong>{{ item.alias }}</strong>
          <small>{{ item.kind }}</small>
        </button>
      </div>
      <div class="manual-register">
        <input v-model="assetName" placeholder="图片名称" />
        <input v-model="assetUrl" placeholder="项目资产 URL 或对象 key" />
        <button type="button" class="ghost-btn small" @click="submitRegister">登记项目资产图</button>
      </div>
      <footer>
        <button type="button" class="primary-btn" @click="submit">添加已选</button>
      </footer>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Add thumbnail rail to GenerationPanel**

Modify `frontend/src/components/generation/GenerationPanel.vue`:

- Import `ReferencePickerModal`.
- Add `pickerOpen = ref(false)`.
- Add `maxReferences = 6` from config or a local constant until settings are exposed.
- Add `addReferences(items)` that appends non-duplicates up to `maxReferences`, applies unique aliases, and calls `store.updateRenderDraft`.
- Add `registerManualReference(payload)` that calls `store.registerManualReference`, then `addReferences([row])`.
- Move reference markup above textarea.
- Add `data-testid="reference-rail"` to the rail.
- Add thumbnail click handling: clicking a reference inserts `@${item.alias ?? item.name}` at the current textarea cursor.
- Add order controls or drag/drop. If implementing without a drag library, use small up/down icon buttons with `data-testid="move-reference-up-${item.id}"` and `data-testid="move-reference-down-${item.id}"`; the final `draftReferences` array order is the provider reference order.
- Disable the add button when `draftReferences.length >= maxReferences` and show “当前模型最多支持 6 张参考图”.
- Disable the generate-video button when `draftReferences.length === 0` and show the existing “至少保留 1 张参考图后才能生成视频” inline copy.
- Before deleting a reference, check whether the prompt contains `@${item.alias ?? item.name}`. If it does, show a confirmation; on confirm, remove both the reference and that mention text. If canceled, keep both unchanged.
- Use delete test ids:

```vue
<button
  class="ghost-btn small"
  type="button"
  :data-testid="`remove-reference-${item.id}`"
  @click="removeReference(item.id)"
>
  删除
</button>
```

Add tests in `generation.panel.spec.ts` for these concrete assertions:

- Clicking a thumbnail for `长安殿` updates the draft prompt to include `@长安殿`.
- Mounting with six references disables the add button and shows `当前模型最多支持 6 张参考图`.
- Clicking `move-reference-up-scene:s1` / `move-reference-down-scene:s1` changes the stored `references` array order.
- When the prompt contains `@长安殿`, canceling the delete confirmation keeps both the reference and the prompt mention.

- [ ] **Step 5: Run panel tests**

Run:

```bash
cd frontend
npm run test -- generation.panel.spec.ts
```

Expected: selected panel tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/generation/ReferencePickerModal.vue frontend/src/components/generation/GenerationPanel.vue frontend/tests/unit/generation.panel.spec.ts
git commit -m "feat(frontend): add shot reference picker"
```

## Task 7: Frontend `@` Mention Menu

**Files:**
- Create: `frontend/src/components/generation/ReferenceMentionMenu.vue`
- Modify: `frontend/src/components/generation/GenerationPanel.vue`
- Test: `frontend/tests/unit/reference.mention.spec.ts`
- Test: `frontend/tests/unit/generation.panel.spec.ts`

- [ ] **Step 1: Write mention menu test**

Create `frontend/tests/unit/reference.mention.spec.ts`:

```ts
import { mount } from "@vue/test-utils";
import ReferenceMentionMenu from "@/components/generation/ReferenceMentionMenu.vue";

it("filters reference options and emits selected reference", async () => {
  const wrapper = mount(ReferenceMentionMenu, {
    props: {
      open: true,
      query: "秦",
      references: [
        { id: "character:c1", kind: "character", source_id: "c1", name: "秦昭", alias: "秦昭", mention_key: "character:c1", image_url: "https://img" },
        { id: "scene:s1", kind: "scene", source_id: "s1", name: "长安殿", alias: "长安殿", mention_key: "scene:s1", image_url: "https://img" }
      ]
    }
  });

  expect(wrapper.text()).toContain("@秦昭");
  expect(wrapper.text()).not.toContain("@长安殿");
  await wrapper.get("button").trigger("click");
  expect(wrapper.emitted("select")?.[0][0]).toMatchObject({ alias: "秦昭" });
});
```

- [ ] **Step 2: Run mention test and confirm it fails**

Run:

```bash
cd frontend
npm run test -- reference.mention.spec.ts
```

Expected: fail with missing component.

- [ ] **Step 3: Create ReferenceMentionMenu**

Create `frontend/src/components/generation/ReferenceMentionMenu.vue`:

```vue
<script setup lang="ts">
import { computed } from "vue";
import type { RenderSubmitReference } from "@/types/api";

const props = defineProps<{
  open: boolean;
  query: string;
  references: RenderSubmitReference[];
}>();

const emit = defineEmits<{ select: [item: RenderSubmitReference] }>();

const rows = computed(() =>
  props.references.filter((item) => {
    const label = item.alias ?? item.name;
    return label.includes(props.query);
  })
);
</script>

<template>
  <div v-if="open" class="mention-menu" data-testid="mention-menu">
    <div v-if="!references.length" class="empty-inline">先添加参考图</div>
    <button v-for="item in rows" :key="item.id" type="button" class="mention-option" @click="emit('select', item)">
      <img :src="item.image_url" :alt="item.name" />
      <span>@{{ item.alias ?? item.name }}</span>
      <small>{{ item.kind }}</small>
    </button>
  </div>
</template>
```

- [ ] **Step 4: Add mention behavior to GenerationPanel**

Modify `frontend/src/components/generation/GenerationPanel.vue`:

- Import `ReferenceMentionMenu`.
- Add state:

```ts
const mentionOpen = ref(false);
const mentionQuery = ref("");
const promptEl = ref<HTMLTextAreaElement | null>(null);
```

- Replace textarea `@input` handler with:

```ts
function onPromptInputEvent(event: Event) {
  const target = event.target as HTMLTextAreaElement;
  const value = target.value;
  onPromptInput(value);
  const cursor = target.selectionStart ?? value.length;
  const prefix = value.slice(0, cursor);
  const match = prefix.match(/@([\u4e00-\u9fa5\w-]*)$/);
  mentionOpen.value = Boolean(match);
  mentionQuery.value = match?.[1] ?? "";
}
```

- Add select handler:

```ts
function selectMention(item: RenderSubmitReference) {
  const label = item.alias ?? item.name;
  const el = promptEl.value;
  if (!el) return;
  const cursor = el.selectionStart ?? draftPrompt.value.length;
  const before = draftPrompt.value.slice(0, cursor).replace(/@([\u4e00-\u9fa5\w-]*)$/, `@${label}`);
  const after = draftPrompt.value.slice(cursor);
  const next = `${before}${after}`;
  draftPrompt.value = next;
  onPromptInput(next);
  mentionOpen.value = false;
}
```

- Update textarea:

```vue
<textarea
  ref="promptEl"
  @input="onPromptInputEvent"
/>
<ReferenceMentionMenu
  :open="mentionOpen"
  :query="mentionQuery"
  :references="draftReferences"
  @select="selectMention"
/>
```

- [ ] **Step 5: Run mention and panel tests**

Run:

```bash
cd frontend
npm run test -- reference.mention.spec.ts generation.panel.spec.ts
```

Expected: selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/generation/ReferenceMentionMenu.vue frontend/src/components/generation/GenerationPanel.vue frontend/tests/unit/reference.mention.spec.ts frontend/tests/unit/generation.panel.spec.ts
git commit -m "feat(frontend): add reference mention picker"
```

## Task 8: Frontend Adaptive Progress Display

**Files:**
- Modify: `frontend/src/composables/useJobPolling.ts`
- Modify: `frontend/src/components/generation/GenerationPanel.vue`
- Test: `frontend/tests/unit/useJobPolling.spec.ts`
- Test: `frontend/tests/unit/generation.panel.spec.ts`

- [ ] **Step 1: Update polling test for display progress**

Append to `frontend/tests/unit/useJobPolling.spec.ts`:

```ts
it("passes adaptive progress fields through onProgress", async () => {
  vi.useFakeTimers();
  const jobId = ref("job1");
  const onProgress = vi.fn();
  const fetcher = vi.fn().mockResolvedValueOnce({
    ...baseJob,
    status: "running",
    progress: 20,
    display_progress: 64,
    estimated_remaining_seconds: 30,
    estimated_source: "recent_20"
  });

  useJobPolling(jobId, { onProgress, onSuccess: () => {}, onError: () => {} }, fetcher);
  await vi.advanceTimersByTimeAsync(2000);

  expect(onProgress).toHaveBeenCalledWith(expect.objectContaining({ display_progress: 64 }));
  vi.useRealTimers();
});
```

- [ ] **Step 2: Run polling test**

Run:

```bash
cd frontend
npm run test -- useJobPolling.spec.ts
```

Expected: pass if `JobState` types are correct.

- [ ] **Step 3: Store adaptive progress in active render shot**

Modify `frontend/src/store/workbench.ts` active render polling/marking logic so `onProgress` can patch the selected render shot with:

```ts
progress: job.display_progress ?? job.progress,
estimatedRemainingSeconds: job.estimated_remaining_seconds ?? null,
estimatedSource: job.estimated_source ?? null,
```

If the store currently only reads `queue.progress` from project aggregate, add a method:

```ts
function applyRenderJobProgress(job: JobState) {
  if (!job.target_id) return;
  renderProgressOverrides.value[job.target_id] = {
    progress: job.display_progress ?? job.progress,
    estimatedRemainingSeconds: job.estimated_remaining_seconds ?? null,
    estimatedSource: job.estimated_source ?? null,
  };
}
```

Call it from `GenerationPanel` `useJobPolling(activeRenderJobId, { onProgress })`.

- [ ] **Step 4: Update GenerationPanel progress copy**

In `GenerationPanel.vue`, change progress display to:

```vue
<div class="progress-head">
  <strong>镜头生成中</strong>
  <span>{{ renderProgress }}%</span>
</div>
<p v-if="selectedRenderShot.estimatedRemainingSeconds != null" class="progress-copy">
  预计剩余约 {{ formatRemaining(selectedRenderShot.estimatedRemainingSeconds) }}
  <span v-if="selectedRenderShot.estimatedSource === 'default'"> · 使用默认估算</span>
  <span v-else> · 基于{{ formatEstimateSource(selectedRenderShot.estimatedSource) }}</span>
</p>
```

Add helper:

```ts
function formatRemaining(seconds: number) {
  if (seconds < 60) return `${seconds} 秒`;
  return `${Math.ceil(seconds / 60)} 分钟`;
}

function formatEstimateSource(source: string | null | undefined) {
  const match = source?.match(/^recent_(\d+)$/);
  return match ? `最近 ${match[1]} 条同类任务` : "最近同类任务";
}
```

- [ ] **Step 5: Add panel assertion**

Append to `frontend/tests/unit/generation.panel.spec.ts`:

```ts
it("shows adaptive remaining time when active render job reports estimate", async () => {
  const store = useWorkbenchStore();
  store.current = makeProject({ stage_raw: "rendering" });
  store.selectedShotId = "SH1";
  store.renderJob = { projectId: "pid", jobId: "job1", shotId: "SH1" };
  store.applyRenderJobProgress({
    id: "job1",
    kind: "render_shot_video",
    status: "running",
    progress: 20,
    display_progress: 64,
    estimated_remaining_seconds: 35,
    estimated_source: "recent_20",
    total: null,
    done: 0,
    payload: null,
    result: null,
    error_msg: null,
    created_at: new Date().toISOString(),
    finished_at: null,
    target_id: "SH1"
  });

  const wrapper = mount(GenerationPanel, { global: testPlugins() });

  expect(wrapper.text()).toContain("64%");
  expect(wrapper.text()).toContain("预计剩余约 35 秒");
});
```

- [ ] **Step 6: Run frontend progress tests**

Run:

```bash
cd frontend
npm run test -- useJobPolling.spec.ts generation.panel.spec.ts
```

Expected: selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/composables/useJobPolling.ts frontend/src/store/workbench.ts frontend/src/components/generation/GenerationPanel.vue frontend/tests/unit/useJobPolling.spec.ts frontend/tests/unit/generation.panel.spec.ts
git commit -m "feat(frontend): show adaptive render progress"
```

## Task 9: Documentation and Verification

**Files:**
- Modify: `frontend/README.md`
- Modify: `backend/README.md`
- Optional Modify: `frontend/scripts/smoke_m3b.sh`

- [ ] **Step 1: Update README notes**

Add to `backend/README.md` M3b section:

```markdown
M3b+ adds shot reference candidates and adaptive job progress:

- `GET /api/v1/projects/{project_id}/shots/{shot_id}/reference-candidates`
- `POST /api/v1/projects/{project_id}/shots/{shot_id}/reference-assets`
- `GET /api/v1/jobs/{job_id}` returns `display_progress` and estimate fields.
```

Add to `frontend/README.md` M3b section:

```markdown
M3b+ reference binding:

- The generation panel shows selected reference thumbnails above the prompt.
- Type `@` in the prompt to bind selected references by alias.
- Render progress uses backend `display_progress` when present.
```

- [ ] **Step 2: Run backend focused tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_reference_schema.py tests/unit/test_job_progress_estimator.py tests/unit/test_schema_validation.py tests/unit/test_shot_video_service.py tests/integration/test_shot_reference_api.py tests/integration/test_jobs_api.py tests/integration/test_render_shot_video_flow.py -v
```

Expected: all selected tests pass.

- [ ] **Step 3: Run backend lint/type checks**

Run:

```bash
cd backend
./.venv/bin/ruff check app tests
./.venv/bin/mypy
```

Expected: both pass.

- [ ] **Step 4: Run frontend focused tests**

Run:

```bash
cd frontend
npm run test -- shots.api.spec.ts workbench.m3b.store.spec.ts generation.panel.spec.ts reference.mention.spec.ts useJobPolling.spec.ts
```

Expected: all selected tests pass.

- [ ] **Step 5: Run frontend type/lint/build**

Run:

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```

Expected: all pass.

- [ ] **Step 6: Run smoke if local stack is available**

Use the repo dev terminal helper, not direct background processes:

```bash
script/dev_terminal.sh open
script/dev_terminal.sh send "cd /Users/macbook/Documents/trae_projects/comic-drama-platform && script/start_all.sh"
script/dev_terminal.sh status
```

Then run the relevant M3b smoke:

```bash
cd frontend
PID=<scenes_locked_project_id> ./scripts/smoke_m3b.sh
```

Expected: smoke completes through draft/reference/video path. If no `scenes_locked_project_id` is available, record that smoke was not run and why.

- [ ] **Step 7: Commit docs and smoke updates**

```bash
git add backend/README.md frontend/README.md frontend/scripts/smoke_m3b.sh
git commit -m "docs: document shot reference binding progress"
```

## Self-Review Checklist

- Spec §5 reference thumbnail rail maps to Task 6.
- Spec §5.3 `@` dropdown maps to Task 7.
- Spec §6 binding snapshot maps to Task 3.
- Spec §7 adaptive progress maps to Task 4 and Task 8.
- Spec §9 config maps to Task 4.
- Spec §10 API suggestions map to Task 1, Task 2, and Task 4.
- Spec §11 acceptance maps to Task 9 verification.
- Manual references are persisted in `project_reference_assets`, rejected unless they belong to the current project asset domain, and reappear in `GET /reference-candidates`.
- History candidates are generated from successful `ShotRender.image_url` and `ShotVideoRender.last_frame_url`.
- Adaptive progress freezes failed/canceled jobs at `finished_at`, normalizes naive datetimes as UTC, and groups video estimates by model type, resolution, and duration.
- Image render and video render both persist and consume `reference_mentions` / `reference_binding_text`.
- UI tasks cover thumbnail mention insertion, reference ordering, max-count enforcement, duplicate alias disambiguation, and delete-confirmation for referenced images.

Known implementation constraint: manual reference registration is project-asset-URL/object-key based in this plan. Multipart binary upload remains a follow-up unless an existing upload abstraction is discovered; if it is discovered, preserve the same response DTO and replace only the endpoint body.

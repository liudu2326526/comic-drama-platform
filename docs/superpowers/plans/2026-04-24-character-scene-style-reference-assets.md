# Character and Scene Style Reference Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build project-level character and scene visual reference images, upgrade character assets to full-body plus headshot images, and force generated scene assets to be no-person environment references.

**Architecture:** Persist project-level visual reference state on `projects`, persist character dual images on `characters`, and keep all remote image generation inside Celery tasks. The frontend reads everything through the existing project aggregate payload, starts generation through thin async endpoints, and reattaches to running jobs through the workbench store.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Celery, Volcengine Ark image generation, Huawei OBS asset storage, Vue 3, TypeScript, Pinia, Vitest.

---

## Source Design

- Product and engineering spec: `docs/superpowers/specs/2026-04-24-character-style-reference-design.md`
- Current character task: `backend/app/tasks/ai/gen_character_asset.py`
- Current scene task: `backend/app/tasks/ai/gen_scene_asset.py`
- Prompt builders: `backend/app/tasks/ai/prompt_builders.py`
- Aggregated project response: `backend/app/domain/services/aggregate_service.py`
- Character UI: `frontend/src/components/character/CharacterAssetsPanel.vue`
- Scene UI: `frontend/src/components/scene/SceneAssetsPanel.vue`
- Store orchestration: `frontend/src/store/workbench.ts`

## Scope

This plan includes:

- Project-level `characterStyleReference` and `sceneStyleReference` state.
- Async generation endpoints and Celery tasks for both project-level visual references.
- Character generation producing two white-background images: full-body and headshot.
- Scene generation prompt and provider request that explicitly forbid people.
- Frontend reference cards, job progress, aggregate hydration, and refresh recovery.
- Reference candidate updates so shot generation can choose character full-body, character headshot, and no-person scene images.

This plan does not include:

- User-uploaded project-level style references.
- Multiple active style reference versions.
- Automatic computer-vision detection and removal of people from scene images.
- Cross-project reuse of style reference images.

## File Structure

Backend create:

- `backend/alembic/versions/e5f6a7b8c9d0_add_style_reference_assets.py` - migration for new `projects` and `characters` columns.
- `backend/app/api/style_references.py` - two async HTTP endpoints for project-level visual reference generation.
- `backend/app/domain/schemas/style_reference.py` - request/response DTOs for visual reference jobs and aggregate state.
- `backend/app/domain/services/style_reference_service.py` - project lookup, stage gate, running-job conflict checks, job creation, and dispatch.
- `backend/app/tasks/ai/gen_style_reference.py` - Celery tasks for character and scene project-level reference generation.
- `backend/app/tasks/ai/__init__.py` - import new tasks so Celery include `app.tasks.ai` registers them.
- `backend/tests/integration/test_style_reference_api.py` - endpoint and persistence tests.
- `backend/tests/unit/test_visual_reference_prompts.py` - prompt constraint tests.

Backend modify:

- `backend/app/domain/models/project.py` - add project-level reference fields.
- `backend/app/domain/models/character.py` - add `full_body_image_url` and `headshot_image_url`.
- `backend/app/domain/models/job.py` - add `gen_character_style_reference` and `gen_scene_style_reference` job kinds.
- `backend/app/infra/asset_store.py` - allow new generated asset kinds and keep using existing async persistence helper.
- `backend/app/domain/schemas/project.py` - include style reference aggregate fields.
- `backend/app/domain/schemas/character.py` - include character dual image URLs.
- `backend/app/domain/services/aggregate_service.py` - output new fields and old-data fallbacks.
- `backend/app/domain/services/reference_candidates.py` - expose character full-body/headshot and scene no-person candidates.
- `backend/app/tasks/ai/prompt_builders.py` - add style reference, character full-body/headshot, and no-person scene prompts.
- `backend/app/tasks/ai/__init__.py` - export `gen_character_style_reference` and `gen_scene_style_reference`.
- `backend/app/tasks/ai/gen_character_asset.py` - generate and persist dual character images.
- `backend/app/tasks/ai/gen_scene_asset.py` - enforce no-person scene generation and use project scene style reference when available.
- `backend/app/api/main.py` or `backend/app/main.py` - include the style reference router, following the current router registration location.

Frontend create:

- `frontend/src/api/styleReferences.ts` - async endpoint wrappers.
- `frontend/src/components/common/StyleReferenceCard.vue` - reusable project-level visual reference card.
- `frontend/tests/unit/style-reference-card.spec.ts` - card state and action tests.

Frontend modify:

- `frontend/src/types/api.ts` - API DTOs for style references and character dual image fields.
- `frontend/src/types/index.ts` - app-level `ProjectData`, `CharacterAsset`, and style reference types.
- `frontend/src/store/workbench.ts` - job IDs, generation actions, polling reattach, and aggregate hydration.
- `frontend/src/components/character/CharacterAssetsPanel.vue` - top dual-column layout and character dual-image display.
- `frontend/src/components/scene/SceneAssetsPanel.vue` - top dual-column layout and no-person scene labeling.
- `frontend/src/styles/global.css` or the component scoped styles - shared visual treatment that matches the existing dark product tone.
- Existing relevant Vitest files under `frontend/tests/unit/` - add coverage for store and panel behavior.

---

## Task 1: Backend Schema and Migration

**Files:**

- Create: `backend/alembic/versions/e5f6a7b8c9d0_add_style_reference_assets.py`
- Modify: `backend/app/domain/models/project.py`
- Modify: `backend/app/domain/models/character.py`
- Modify: `backend/app/domain/models/job.py`
- Modify: `backend/app/infra/asset_store.py`
- Test: `backend/tests/unit/test_style_reference_schema.py`

- [ ] **Step 1: Write a failing schema test**

Create `backend/tests/unit/test_style_reference_schema.py`:

```python
from app.domain.models import Character, Job, Project
from app.infra.asset_store import ALLOWED_KINDS


def test_project_has_style_reference_fields():
    project = Project(name="p", novel_text="n")

    assert hasattr(project, "character_style_reference_image_url")
    assert hasattr(project, "character_style_reference_prompt")
    assert hasattr(project, "character_style_reference_status")
    assert hasattr(project, "character_style_reference_error")
    assert hasattr(project, "scene_style_reference_image_url")
    assert hasattr(project, "scene_style_reference_prompt")
    assert hasattr(project, "scene_style_reference_status")
    assert hasattr(project, "scene_style_reference_error")


def test_character_has_dual_image_fields():
    character = Character(project_id="p1", name="秦昭", role_type="protagonist")

    assert hasattr(character, "full_body_image_url")
    assert hasattr(character, "headshot_image_url")


def test_job_kinds_include_style_reference_generation():
    assert "gen_character_style_reference" in Job.JOB_KIND_VALUES
    assert "gen_scene_style_reference" in Job.JOB_KIND_VALUES


def test_asset_store_allows_new_generated_asset_kinds():
    assert "character_style_reference" in ALLOWED_KINDS
    assert "scene_style_reference" in ALLOWED_KINDS
    assert "character_full_body" in ALLOWED_KINDS
    assert "character_headshot" in ALLOWED_KINDS
```

- [ ] **Step 2: Run the schema test and verify it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_style_reference_schema.py -v
```

Expected: fails because the new model attributes and job kinds do not exist.

- [ ] **Step 3: Add model fields**

In `backend/app/domain/models/project.py`, add nullable columns to the `Project` model:

```python
character_style_reference_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
character_style_reference_prompt: Mapped[dict | None] = mapped_column(JSON, nullable=True)
character_style_reference_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
character_style_reference_error: Mapped[str | None] = mapped_column(Text, nullable=True)

scene_style_reference_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
scene_style_reference_prompt: Mapped[dict | None] = mapped_column(JSON, nullable=True)
scene_style_reference_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
scene_style_reference_error: Mapped[str | None] = mapped_column(Text, nullable=True)
```

In `backend/app/domain/models/character.py`, add:

```python
full_body_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
headshot_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

In `backend/app/domain/models/job.py`, add both values to `JOB_KIND_VALUES`:

```python
"gen_character_style_reference",
"gen_scene_style_reference",
```

In `backend/app/infra/asset_store.py`, expand the existing allowed kinds:

```python
ALLOWED_KINDS = {
    "character",
    "scene",
    "shot",
    "character_style_reference",
    "scene_style_reference",
    "character_full_body",
    "character_headshot",
}
```

- [ ] **Step 4: Add Alembic migration**

Create `backend/alembic/versions/e5f6a7b8c9d0_add_style_reference_assets.py`:

```python
"""add style reference assets

Revision ID: e5f6a7b8c9d0
Revises: d4f5a6b7c8d9
Create Date: 2026-04-24 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("character_style_reference_image_url", sa.String(length=512), nullable=True))
    op.add_column("projects", sa.Column("character_style_reference_prompt", sa.JSON(), nullable=True))
    op.add_column("projects", sa.Column("character_style_reference_status", sa.String(length=32), nullable=True))
    op.add_column("projects", sa.Column("character_style_reference_error", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("scene_style_reference_image_url", sa.String(length=512), nullable=True))
    op.add_column("projects", sa.Column("scene_style_reference_prompt", sa.JSON(), nullable=True))
    op.add_column("projects", sa.Column("scene_style_reference_status", sa.String(length=32), nullable=True))
    op.add_column("projects", sa.Column("scene_style_reference_error", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("full_body_image_url", sa.String(length=512), nullable=True))
    op.add_column("characters", sa.Column("headshot_image_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("characters", "headshot_image_url")
    op.drop_column("characters", "full_body_image_url")
    op.drop_column("projects", "scene_style_reference_error")
    op.drop_column("projects", "scene_style_reference_status")
    op.drop_column("projects", "scene_style_reference_prompt")
    op.drop_column("projects", "scene_style_reference_image_url")
    op.drop_column("projects", "character_style_reference_error")
    op.drop_column("projects", "character_style_reference_status")
    op.drop_column("projects", "character_style_reference_prompt")
    op.drop_column("projects", "character_style_reference_image_url")
```

- [ ] **Step 5: Run schema test and migration check**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_style_reference_schema.py -v
./.venv/bin/alembic upgrade head
```

Expected: test passes and migration applies cleanly.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/models/project.py backend/app/domain/models/character.py backend/app/domain/models/job.py backend/app/infra/asset_store.py backend/alembic/versions/e5f6a7b8c9d0_add_style_reference_assets.py backend/tests/unit/test_style_reference_schema.py
git commit -m "feat(backend): add style reference asset schema"
```

---

## Task 2: Backend DTOs and Aggregate Output

**Files:**

- Create: `backend/app/domain/schemas/style_reference.py`
- Modify: `backend/app/domain/schemas/project.py`
- Modify: `backend/app/domain/schemas/character.py`
- Modify: `backend/app/domain/services/aggregate_service.py`
- Test: `backend/tests/integration/test_style_reference_aggregate.py`

- [ ] **Step 1: Write failing aggregate tests**

Create `backend/tests/integration/test_style_reference_aggregate.py`:

```python
import pytest

from app.domain.models import Character, Project, ProjectStage, Scene
from app.domain.services.aggregate_service import AggregateService
from app.infra.asset_store import build_asset_url


@pytest.mark.asyncio
async def test_aggregate_includes_style_references_and_dual_character_images(db_session):
    project = Project(
        name="雨夜",
        novel_text="雨夜皇城",
        stage=ProjectStage.SCENES_LOCKED,
        character_style_reference_image_url="projects/p1/style/character.png",
        character_style_reference_prompt={"prompt": "角色母版 prompt"},
        character_style_reference_status="succeeded",
        scene_style_reference_image_url="projects/p1/style/scene.png",
        scene_style_reference_prompt={"prompt": "场景母版 prompt"},
        scene_style_reference_status="succeeded",
    )
    db_session.add(project)
    await db_session.flush()

    character = Character(
        project_id=project.id,
        name="秦昭",
        role_type="protagonist",
        full_body_image_url="projects/p1/characters/qinzhao-full.png",
        headshot_image_url="projects/p1/characters/qinzhao-head.png",
        reference_image_url="projects/p1/characters/legacy.png",
    )
    scene = Scene(
        project_id=project.id,
        name="宫门",
        theme="palace",
        reference_image_url="projects/p1/scenes/gate.png",
    )
    db_session.add_all([character, scene])
    await db_session.commit()

    detail = await AggregateService(db_session).get_project_detail(project.id)
    data = detail.model_dump(mode="json")

    assert data["characterStyleReference"]["imageUrl"] == build_asset_url("projects/p1/style/character.png")
    assert data["characterStyleReference"]["prompt"] == "角色母版 prompt"
    assert data["characterStyleReference"]["status"] == "succeeded"
    assert data["sceneStyleReference"]["imageUrl"] == build_asset_url("projects/p1/style/scene.png")
    assert data["sceneStyleReference"]["prompt"] == "场景母版 prompt"
    assert data["sceneStyleReference"]["status"] == "succeeded"
    assert data["characters"][0]["full_body_image_url"] == build_asset_url("projects/p1/characters/qinzhao-full.png")
    assert data["characters"][0]["headshot_image_url"] == build_asset_url("projects/p1/characters/qinzhao-head.png")
    assert data["characters"][0]["reference_image_url"] == build_asset_url("projects/p1/characters/qinzhao-full.png")
    assert data["scenes"][0]["reference_image_url"] == build_asset_url("projects/p1/scenes/gate.png")


@pytest.mark.asyncio
async def test_aggregate_falls_back_to_legacy_character_reference_image(db_session):
    project = Project(name="旧项目", novel_text="n", stage=ProjectStage.CHARACTERS_LOCKED)
    db_session.add(project)
    await db_session.flush()
    db_session.add(
        Character(
            project_id=project.id,
            name="旧角色",
            role_type="supporting",
            reference_image_url="projects/p1/characters/legacy.png",
        )
    )
    await db_session.commit()

    detail = await AggregateService(db_session).get_project_detail(project.id)
    data = detail.model_dump(mode="json")

    assert data["characterStyleReference"]["imageUrl"] is None
    assert data["characterStyleReference"]["status"] == "empty"
    assert data["characters"][0]["full_body_image_url"] == build_asset_url("projects/p1/characters/legacy.png")
    assert data["characters"][0]["reference_image_url"] == build_asset_url("projects/p1/characters/legacy.png")
```

- [ ] **Step 2: Run aggregate tests and verify they fail**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_style_reference_aggregate.py -v
```

Expected: fails because aggregate fields are not emitted.

- [ ] **Step 3: Add schema DTOs**

Create `backend/app/domain/schemas/style_reference.py`:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict


StyleReferenceStatus = Literal["empty", "running", "succeeded", "failed"]
StyleReferenceKind = Literal["character", "scene"]


class StyleReferenceState(BaseModel):
    imageUrl: str | None = None
    prompt: str | None = None
    status: StyleReferenceStatus = "empty"
    error: str | None = None

    model_config = ConfigDict(from_attributes=True)


class StyleReferenceJobAck(BaseModel):
    job_id: str


def prompt_text(snapshot: dict | None) -> str | None:
    if not snapshot:
        return None
    value = snapshot.get("prompt")
    return value if isinstance(value, str) else None
```

In `backend/app/domain/schemas/project.py`, import and include:

```python
from app.domain.schemas.style_reference import StyleReferenceState
```

Add to the aggregate project DTO if a strict Pydantic response model exists:

```python
characterStyleReference: StyleReferenceState
sceneStyleReference: StyleReferenceState
```

In `backend/app/domain/schemas/character.py`, add:

```python
full_body_image_url: str | None = None
headshot_image_url: str | None = None
```

- [ ] **Step 4: Update aggregate output**

In `backend/app/domain/services/aggregate_service.py`, add helper methods near existing private helper methods:

```python
from app.domain.schemas.style_reference import prompt_text
from app.infra.asset_store import build_asset_url


def _style_reference_state(project: Project, kind: str) -> dict:
    if kind == "character":
        image_key = project.character_style_reference_image_url
        snapshot = project.character_style_reference_prompt
        status = project.character_style_reference_status
        error = project.character_style_reference_error
    else:
        image_key = project.scene_style_reference_image_url
        snapshot = project.scene_style_reference_prompt
        status = project.scene_style_reference_status
        error = project.scene_style_reference_error

    return {
        "imageUrl": build_asset_url(image_key) if image_key else None,
        "prompt": prompt_text(snapshot),
        "status": status or "empty",
        "error": error,
    }
```

When building the project detail dict, include:

```python
"characterStyleReference": _style_reference_state(project, "character"),
"sceneStyleReference": _style_reference_state(project, "scene"),
```

When building each character dict, use full-body fallback:

```python
full_body_key = c.full_body_image_url or c.reference_image_url
"reference_image_url": build_asset_url(full_body_key) if full_body_key else None,
"full_body_image_url": build_asset_url(full_body_key) if full_body_key else None,
"headshot_image_url": build_asset_url(c.headshot_image_url) if c.headshot_image_url else None,
```

- [ ] **Step 5: Run aggregate tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_style_reference_aggregate.py -v
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/schemas/style_reference.py backend/app/domain/schemas/project.py backend/app/domain/schemas/character.py backend/app/domain/services/aggregate_service.py backend/tests/integration/test_style_reference_aggregate.py
git commit -m "feat(backend): expose visual reference aggregate state"
```

---

## Task 3: Project-Level Style Reference API and Service

**Files:**

- Create: `backend/app/domain/services/style_reference_service.py`
- Create: `backend/app/api/style_references.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/tasks/ai/__init__.py`
- Test: `backend/tests/integration/test_style_reference_api.py`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/integration/test_style_reference_api.py`:

```python
import pytest

from app.domain.models import Job, Project, ProjectStage


@pytest.mark.asyncio
async def test_create_character_style_reference_job(client, db_session, monkeypatch):
    dispatched: list[tuple[str, str]] = []

    class FakeTask:
        def delay(self, project_id: str, job_id: str):
            dispatched.append((project_id, job_id))
            return type("Result", (), {"id": "celery-character"})()

    monkeypatch.setattr("app.api.style_references.gen_character_style_reference", FakeTask())

    project = Project(name="雨夜", novel_text="n", stage=ProjectStage.STORYBOARD_READY)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    resp = await client.post(f"/api/v1/projects/{project.id}/character-style-reference/generate")

    assert resp.status_code == 200
    job_id = resp.json()["data"]["job_id"]
    job = await db_session.get(Job, job_id)
    assert job is not None
    assert job.kind == "gen_character_style_reference"
    assert job.project_id == project.id
    assert dispatched == [(project.id, job_id)]


@pytest.mark.asyncio
async def test_create_scene_style_reference_job(client, db_session, monkeypatch):
    dispatched: list[tuple[str, str]] = []

    class FakeTask:
        def delay(self, project_id: str, job_id: str):
            dispatched.append((project_id, job_id))
            return type("Result", (), {"id": "celery-scene"})()

    monkeypatch.setattr("app.api.style_references.gen_scene_style_reference", FakeTask())

    project = Project(name="雨夜", novel_text="n", stage=ProjectStage.CHARACTERS_LOCKED)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    resp = await client.post(f"/api/v1/projects/{project.id}/scene-style-reference/generate")

    assert resp.status_code == 200
    job_id = resp.json()["data"]["job_id"]
    job = await db_session.get(Job, job_id)
    assert job.kind == "gen_scene_style_reference"
    assert dispatched == [(project.id, job_id)]


@pytest.mark.asyncio
async def test_style_reference_rejects_duplicate_running_job(client, db_session):
    project = Project(name="雨夜", novel_text="n", stage=ProjectStage.STORYBOARD_READY)
    db_session.add(project)
    await db_session.flush()
    db_session.add(
        Job(
            project_id=project.id,
            kind="gen_character_style_reference",
            status="running",
            progress=20,
            done=0,
            total=1,
        )
    )
    await db_session.commit()
    await db_session.refresh(project)

    resp = await client.post(f"/api/v1/projects/{project.id}/character-style-reference/generate")

    assert resp.status_code == 409
    assert resp.json()["code"] == 40901
```

- [ ] **Step 2: Run API tests and verify they fail**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_style_reference_api.py -v
```

Expected: import or route failures because the new service/router does not exist.

- [ ] **Step 3: Implement service**

Create `backend/app/domain/services/style_reference_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.domain.models import Job, Project
from app.domain.schemas.style_reference import StyleReferenceKind
from app.pipeline.transitions import assert_asset_editable


class StyleReferenceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_generation_job(self, project_id: str, kind: StyleReferenceKind) -> Job:
        project = await self.session.get(Project, project_id)
        if project is None:
            raise ApiError(40401, "项目不存在", 404)

        if kind == "character":
            assert_asset_editable(project, "character")
            job_kind = "gen_character_style_reference"
            error_attr = "character_style_reference_error"
        else:
            assert_asset_editable(project, "scene")
            job_kind = "gen_scene_style_reference"
            error_attr = "scene_style_reference_error"

        running = await self.session.scalar(
            select(Job).where(
                Job.project_id == project_id,
                Job.kind == job_kind,
                (
                    (Job.status == "running")
                    | ((Job.status == "queued") & Job.celery_task_id.is_not(None))
                ),
            )
        )
        if running is not None:
            raise ApiError(40901, "已有同类参考图任务正在运行", 409)

        setattr(project, error_attr, None)
        job = Job(
            project_id=project_id,
            kind=job_kind,
            status="queued",
            progress=10,
            done=0,
            total=1,
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job
```

Do not write `project.*_status="running"` in this service. The task writes `running` after it actually starts. The duplicate check only blocks running jobs or queued jobs with a recorded `celery_task_id`; this avoids permanently blocking retry when the HTTP process commits the Job and then crashes before Celery dispatch.

- [ ] **Step 4: Implement router**

Create `backend/app/api/style_references.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.envelope import Envelope
from app.pipeline.transitions import update_job_progress
from app.domain.schemas.style_reference import StyleReferenceJobAck
from app.domain.services.style_reference_service import StyleReferenceService
from app.deps import get_db
from app.tasks.ai.gen_style_reference import gen_character_style_reference, gen_scene_style_reference

router = APIRouter(prefix="/projects/{project_id}", tags=["style-references"])


@router.post("/character-style-reference/generate", response_model=Envelope[StyleReferenceJobAck])
async def generate_character_style_reference(project_id: str, session: AsyncSession = Depends(get_db)):
    job = await StyleReferenceService(session).create_generation_job(project_id, "character")
    try:
        result = gen_character_style_reference.delay(project_id, job.id)
        job.celery_task_id = result.id
        await session.commit()
    except Exception as exc:
        await update_job_progress(session, job.id, status="failed", error_msg=f"dispatch failed: {exc}")
        await session.commit()
        raise
    return Envelope.success(StyleReferenceJobAck(job_id=job.id))


@router.post("/scene-style-reference/generate", response_model=Envelope[StyleReferenceJobAck])
async def generate_scene_style_reference(project_id: str, session: AsyncSession = Depends(get_db)):
    job = await StyleReferenceService(session).create_generation_job(project_id, "scene")
    try:
        result = gen_scene_style_reference.delay(project_id, job.id)
        job.celery_task_id = result.id
        await session.commit()
    except Exception as exc:
        await update_job_progress(session, job.id, status="failed", error_msg=f"dispatch failed: {exc}")
        await session.commit()
        raise
    return Envelope.success(StyleReferenceJobAck(job_id=job.id))
```

Register the router in `backend/app/main.py` with the same prefix style as existing routers:

```python
from app.api import style_references

app.include_router(style_references.router, prefix="/api/v1")
```

- [ ] **Step 5: Run API tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_style_reference_api.py -v
```

Expected: tests pass once the task module exists in Task 4. If the task import fails before Task 4, create the module shell in Step 6.

- [ ] **Step 6: Add task module shell for router import**

Create `backend/app/tasks/ai/gen_style_reference.py` with temporary task functions that will be completed in Task 4:

```python
from app.tasks.celery_app import celery_app


@celery_app.task(name="ai.gen_character_style_reference")
def gen_character_style_reference(project_id: str, job_id: str) -> None:
    raise NotImplementedError("gen_character_style_reference is implemented in Task 4")


@celery_app.task(name="ai.gen_scene_style_reference")
def gen_scene_style_reference(project_id: str, job_id: str) -> None:
    raise NotImplementedError("gen_scene_style_reference is implemented in Task 4")
```

Update `backend/app/tasks/ai/__init__.py`:

```python
from .gen_style_reference import gen_character_style_reference, gen_scene_style_reference
```

Add both names to `__all__`:

```python
"gen_character_style_reference",
"gen_scene_style_reference",
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/domain/services/style_reference_service.py backend/app/api/style_references.py backend/app/main.py backend/app/tasks/ai/gen_style_reference.py backend/app/tasks/ai/__init__.py backend/tests/integration/test_style_reference_api.py
git commit -m "feat(backend): add style reference generation endpoints"
```

---

## Task 4: Prompt Builders and Project-Level Generation Tasks

**Files:**

- Modify: `backend/app/tasks/ai/prompt_builders.py`
- Modify: `backend/app/tasks/ai/gen_style_reference.py`
- Test: `backend/tests/unit/test_visual_reference_prompts.py`
- Test: `backend/tests/integration/test_style_reference_tasks.py`

- [ ] **Step 1: Write failing prompt tests**

Create `backend/tests/unit/test_visual_reference_prompts.py`:

```python
from app.domain.models import Character, Project, Scene
from app.tasks.ai.prompt_builders import (
    build_character_full_body_prompt,
    build_character_headshot_prompt,
    build_character_style_reference_prompt,
    build_scene_asset_prompt,
    build_scene_style_reference_prompt,
)


def test_character_style_reference_prompt_requires_white_background_full_body():
    project = Project(
        name="雨夜",
        novel_text="n",
        character_prompt_profile_applied={"prompt": "古风权谋,冷雨,厚重服饰"},
    )

    prompt = build_character_style_reference_prompt(project)

    assert "项目级角色风格参考图" in prompt
    assert "白底" in prompt
    assert "正面全身" in prompt
    assert "不是具体剧情角色" in prompt
    assert "禁止" in prompt
    assert "多人" in prompt


def test_scene_style_reference_prompt_strictly_forbids_people():
    project = Project(
        name="雨夜",
        novel_text="n",
        scene_prompt_profile_applied={"prompt": "雨夜皇城,宫墙,湿冷石板"},
    )

    prompt = build_scene_style_reference_prompt(project)

    assert "项目级场景视觉参考图" in prompt
    assert "绝对不出现任何人物" in prompt
    assert "人脸" in prompt
    assert "人群" in prompt
    assert "背影" in prompt
    assert "剪影" in prompt
    assert "身体局部" in prompt


def test_character_dual_prompts_have_different_composition_constraints():
    project = Project(name="雨夜", novel_text="n")
    character = Character(
        project_id="p1",
        name="秦昭",
        role_type="protagonist",
        summary="少年天子",
        description="黑金冕服,克制警惕",
    )

    full_body = build_character_full_body_prompt(project, character)
    headshot = build_character_headshot_prompt(project, character)

    assert "白底正面全身" in full_body
    assert "头顶到脚底完整可见" in full_body
    assert "大头像" in headshot
    assert "五官" in headshot
    assert "脸型" in headshot


def test_scene_asset_prompt_forbids_people():
    project = Project(name="雨夜", novel_text="n")
    scene = Scene(project_id="p1", name="朱雀门", theme="palace", summary="雨夜宫门")

    prompt = build_scene_asset_prompt(project, scene)

    assert "绝对不出现人物" in prompt
    assert "人脸" in prompt
    assert "人群" in prompt
    assert "背影" in prompt
```

- [ ] **Step 2: Run prompt tests and verify they fail**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_visual_reference_prompts.py -v
```

Expected: fails because the new prompt builder functions do not exist and scene prompt is too weak.

- [ ] **Step 3: Implement prompt builders**

In `backend/app/tasks/ai/prompt_builders.py`, add:

```python
def _profile_prompt(value: dict | None) -> str:
    if not value:
        return ""
    prompt = value.get("prompt")
    return prompt if isinstance(prompt, str) else ""


def build_character_style_reference_prompt(project: Project) -> str:
    profile = _profile_prompt(project.character_prompt_profile_applied)
    return (
        "9:16竖版构图。生成项目级角色风格参考图,作为后续所有角色参考图的视觉母版,不是具体剧情角色。"
        "画面为单人正面全身角色设定图,人物居中站立,头顶到脚底完整可见,双臂自然下垂或轻微收拢,"
        "姿态端正自然。背景为纯白色,无场景、无道具、无文字、无边框。\n\n"
        f"项目级角色统一视觉设定:\n{profile or project.novel_text[:1200]}\n\n"
        "要求:体现统一的脸型比例、五官风格、眼神气质、发型质感、肤色处理、时代服装结构、布料材质、"
        "纹样密度、新旧状态和整体色彩体系。白底棚拍式柔和主光,正面与侧前方补光均衡,细节清晰。\n\n"
        "禁止:多人、复杂背景、半身像、头像裁切、侧脸、背影、过度动态姿势、身体遮挡、手脚缺失、"
        "文字、字幕、LOGO、水印、背景非白色、道具抢画面、风格漂移。"
    )


def build_scene_style_reference_prompt(project: Project) -> str:
    profile = _profile_prompt(project.scene_prompt_profile_applied)
    return (
        "16:9横版构图。生成项目级场景视觉参考图,作为后续所有场景参考图的空间风格母版,不是具体剧情镜头。"
        "画面只呈现场景环境,绝对不出现任何人物。重点表现空间结构、时代建筑、环境道具、材质纹理、"
        "灯光氛围、天气状态、色彩体系和镜头景深。\n\n"
        f"项目级场景统一视觉设定:\n{profile or project.novel_text[:1200]}\n\n"
        "要求:宽阔清晰的场景视角,前景、中景、远景层次明确,建筑轮廓稳定,空间入口、墙面、地面、"
        "家具或环境道具关系清楚。主光源方向明确,材质表面反光、潮湿、磨损、灰尘或年代痕迹清楚。\n\n"
        "禁止:人物、人脸、人群、背影、剪影、手脚身体局部、角色站位、人物衣物残影、文字、字幕、LOGO、"
        "水印、现代错置元素、结构混乱、透视崩坏、风格漂移。"
    )
```

Add character dual prompt builders:

```python
def build_character_full_body_prompt(project: Project, char: Character) -> str:
    profile = _profile_prompt(project.character_prompt_profile_applied)
    style_ref = "项目级角色风格参考图已生成,参考其人物画风、身体比例、服装材质、白底全身构图和渲染质感。" if project.character_style_reference_image_url else ""
    return (
        "9:16竖版构图。生成角色全身参考图,用于后续分镜和视频生成中的人物一致性锁定。"
        "画面为单人白底正面全身角色设定图,角色居中站立,头顶到脚底完整可见,姿态自然稳定。\n\n"
        f"角色名称:{char.name}\n角色简介:{char.summary or ''}\n角色详述:{char.description or ''}\n\n"
        f"项目级角色统一视觉设定:\n{profile}\n{style_ref}\n\n"
        "面部、发型、服装、鞋履、配饰、材质和新旧状态必须严格来自角色设定。"
        "禁止:多人、复杂背景、半身像、头像裁切、侧脸、背影、身体遮挡、手脚缺失、文字、字幕、LOGO、水印。"
    )


def build_character_headshot_prompt(project: Project, char: Character) -> str:
    profile = _profile_prompt(project.character_prompt_profile_applied)
    style_ref = "项目级角色风格参考图已生成,参考其脸型比例、五官风格、发型质感和渲染质感。" if project.character_style_reference_image_url else ""
    return (
        "9:16竖版构图。生成角色大头像参考图,用于锁定后续镜头中的脸型、五官、发型、眼神和妆造细节。"
        "画面为单人白底大头像或胸像近景,角色面部占画面主体,头发完整可见,肩颈和服饰领口适度入画。\n\n"
        f"角色名称:{char.name}\n角色简介:{char.summary or ''}\n角色详述:{char.description or ''}\n\n"
        f"项目级角色统一视觉设定:\n{profile}\n{style_ref}\n\n"
        "面部要求:脸型轮廓明确,眼型、眉形、鼻梁、唇形、下颌线、肤色、眼神和皮肤质感清楚。"
        "禁止:多人、复杂背景、全身远景、脸部遮挡、强表情扭曲、五官变形、发型缺失、文字、字幕、LOGO、水印。"
    )
```

Update `build_scene_asset_prompt` so the final constraints include:

```python
"画面要求：16:9横版构图,只呈现场景环境,绝对不出现人物,不出现人脸、人群、背影、剪影或身体局部。\n"
```

- [ ] **Step 4: Write failing task tests**

Create `backend/tests/integration/test_style_reference_tasks.py`:

```python
import pytest

from app.domain.models import Job, Project, ProjectStage
from app.tasks.ai.gen_style_reference import run_character_style_reference, run_scene_style_reference


class FakeImageClient:
    def __init__(self):
        self.calls = []

    async def image_generations(self, model, prompt, **kwargs):
        self.calls.append({"model": model, "prompt": prompt, **kwargs})
        return {"data": [{"url": "https://example.test/image.png"}]}


@pytest.mark.asyncio
async def test_character_style_reference_task_persists_image(db_session, monkeypatch):
    client = FakeImageClient()
    stored = []

    monkeypatch.setattr("app.tasks.ai.gen_style_reference.get_volcano_client", lambda: client)
    async def fake_persist_generated_asset(**kwargs):
        stored.append(kwargs)
        return "projects/p1/style/character.png"

    monkeypatch.setattr("app.tasks.ai.gen_style_reference.persist_generated_asset", fake_persist_generated_asset)

    project = Project(name="雨夜", novel_text="n", stage=ProjectStage.STORYBOARD_READY)
    db_session.add(project)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_character_style_reference", status="queued", progress=10, done=0, total=1)
    db_session.add(job)
    await db_session.commit()

    await run_character_style_reference(project.id, job.id, session=db_session)
    await db_session.refresh(project)
    await db_session.refresh(job)

    assert project.character_style_reference_image_url == "projects/p1/style/character.png"
    assert project.character_style_reference_status == "succeeded"
    assert project.character_style_reference_prompt["prompt"]
    assert job.status == "succeeded"
    assert "白底" in client.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_scene_style_reference_task_persists_no_person_image(db_session, monkeypatch):
    client = FakeImageClient()
    monkeypatch.setattr("app.tasks.ai.gen_style_reference.get_volcano_client", lambda: client)
    async def fake_persist_generated_asset(**kwargs):
        return "projects/p1/style/scene.png"

    monkeypatch.setattr("app.tasks.ai.gen_style_reference.persist_generated_asset", fake_persist_generated_asset)

    project = Project(name="雨夜", novel_text="n", stage=ProjectStage.CHARACTERS_LOCKED)
    db_session.add(project)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_scene_style_reference", status="queued", progress=10, done=0, total=1)
    db_session.add(job)
    await db_session.commit()

    await run_scene_style_reference(project.id, job.id, session=db_session)
    await db_session.refresh(project)

    assert project.scene_style_reference_image_url == "projects/p1/style/scene.png"
    assert project.scene_style_reference_status == "succeeded"
    assert "绝对不出现任何人物" in client.calls[0]["prompt"]
```

- [ ] **Step 5: Implement task runners**

In `backend/app/tasks/ai/gen_style_reference.py`, replace the shell with:

```python
import asyncio
import logging
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.models import Project
from app.infra.asset_store import persist_generated_asset
from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.pipeline.transitions import update_job_progress
from app.tasks.ai.prompt_builders import build_character_style_reference_prompt, build_scene_style_reference_prompt
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_style_reference(
    project_id: str,
    job_id: str,
    *,
    kind: Literal["character", "scene"],
    session: AsyncSession | None = None,
) -> None:
    owns_session = session is None
    if session is None:
        session = get_session_factory()()
    try:
        project = await session.get(Project, project_id)
        if project is None:
            raise RuntimeError(f"project not found: {project_id}")

        await update_job_progress(session, job_id, status="running", progress=30, done=0, total=1)
        if kind == "character":
            project.character_style_reference_status = "running"
            project.character_style_reference_error = None
        else:
            project.scene_style_reference_status = "running"
            project.scene_style_reference_error = None
        await session.commit()

        prompt = build_character_style_reference_prompt(project) if kind == "character" else build_scene_style_reference_prompt(project)
        model = get_settings().ark_image_model
        size = "768x1344" if kind == "character" else "1344x768"

        await update_job_progress(session, job_id, status="running", progress=70, done=0, total=1)
        response = await get_volcano_client().image_generations(model, prompt, n=1, size=size)
        remote_url = response["data"][0]["url"]

        await update_job_progress(session, job_id, status="running", progress=90, done=0, total=1)
        object_key = await persist_generated_asset(
            url=remote_url,
            project_id=project_id,
            kind=f"{kind}_style_reference",
            ext="png",
        )
        snapshot = {"prompt": prompt, "model": model, "size": size, "remote_url": remote_url}
        if kind == "character":
            project.character_style_reference_image_url = object_key
            project.character_style_reference_prompt = snapshot
            project.character_style_reference_status = "succeeded"
            project.character_style_reference_error = None
        else:
            project.scene_style_reference_image_url = object_key
            project.scene_style_reference_prompt = snapshot
            project.scene_style_reference_status = "succeeded"
            project.scene_style_reference_error = None
        await session.commit()
        await update_job_progress(session, job_id, status="succeeded", progress=100, done=1, total=1)
    except Exception as exc:
        logger.exception("style reference generation failed")
        project = await session.get(Project, project_id)
        if project is not None:
            if kind == "character":
                project.character_style_reference_status = "failed"
                project.character_style_reference_error = str(exc)
            else:
                project.scene_style_reference_status = "failed"
                project.scene_style_reference_error = str(exc)
            await session.commit()
        await update_job_progress(session, job_id, status="failed", progress=100, done=0, total=1)
        raise
    finally:
        if owns_session:
            await session.close()


async def run_character_style_reference(project_id: str, job_id: str, *, session: AsyncSession | None = None) -> None:
    await _run_style_reference(project_id, job_id, kind="character", session=session)


async def run_scene_style_reference(project_id: str, job_id: str, *, session: AsyncSession | None = None) -> None:
    await _run_style_reference(project_id, job_id, kind="scene", session=session)


@celery_app.task(name="ai.gen_character_style_reference")
def gen_character_style_reference(project_id: str, job_id: str) -> None:
    asyncio.run(run_character_style_reference(project_id, job_id))


@celery_app.task(name="ai.gen_scene_style_reference")
def gen_scene_style_reference(project_id: str, job_id: str) -> None:
    asyncio.run(run_scene_style_reference(project_id, job_id))
```

The helper names above match the current repository: `persist_generated_asset`, `get_session_factory`, and `update_job_progress` from `app.pipeline.transitions`.

- [ ] **Step 6: Run prompt and task tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_visual_reference_prompts.py tests/integration/test_style_reference_tasks.py -v
```

Expected: tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/tasks/ai/prompt_builders.py backend/app/tasks/ai/gen_style_reference.py backend/tests/unit/test_visual_reference_prompts.py backend/tests/integration/test_style_reference_tasks.py
git commit -m "feat(backend): generate project style reference images"
```

---

## Task 5: Character Dual-Image Generation

**Files:**

- Modify: `backend/app/tasks/ai/gen_character_asset.py`
- Modify: `backend/app/api/characters.py`
- Test: `backend/tests/integration/test_character_dual_image_generation.py`

- [ ] **Step 1: Write failing character generation test**

Create `backend/tests/integration/test_character_dual_image_generation.py`:

```python
import pytest

from app.domain.models import Character, Job, Project, ProjectStage
from app.tasks.ai.gen_character_asset import run_character_asset_generation


class FakeImageClient:
    def __init__(self):
        self.prompts = []

    async def image_generations(self, model, prompt, **kwargs):
        self.prompts.append(prompt)
        index = len(self.prompts)
        return {"data": [{"url": f"https://example.test/character-{index}.png"}]}


@pytest.mark.asyncio
async def test_character_asset_generation_writes_full_body_and_headshot(db_session, monkeypatch):
    client = FakeImageClient()
    stored = []

    monkeypatch.setattr("app.tasks.ai.gen_character_asset.get_volcano_client", lambda: client)

    async def fake_persist_generated_asset(**kwargs):
        key = f"projects/p1/characters/{len(stored) + 1}.png"
        stored.append(key)
        return key

    monkeypatch.setattr("app.tasks.ai.gen_character_asset.persist_generated_asset", fake_persist_generated_asset)

    project = Project(
        name="雨夜",
        novel_text="n",
        stage=ProjectStage.STORYBOARD_READY,
        character_style_reference_image_url="projects/p1/style/character.png",
    )
    db_session.add(project)
    await db_session.flush()
    character = Character(
        project_id=project.id,
        name="秦昭",
        role_type="protagonist",
        summary="少年天子",
        description="黑金冕服",
    )
    db_session.add(character)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_character_asset_single", status="queued", progress=10, done=0, total=1, target_id=character.id, target_type="character")
    db_session.add(job)
    await db_session.commit()

    await run_character_asset_generation(character.id, job.id, session=db_session)
    await db_session.refresh(character)

    assert character.full_body_image_url == "projects/p1/characters/1.png"
    assert character.headshot_image_url == "projects/p1/characters/2.png"
    assert character.reference_image_url == "projects/p1/characters/1.png"
    assert "白底正面全身" in client.prompts[0]
    assert "大头像" in client.prompts[1]
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_character_dual_image_generation.py -v
```

Expected: fails because only one image is generated.

- [ ] **Step 3: Refactor task to expose async runner**

In `backend/app/tasks/ai/gen_character_asset.py`, keep the existing Celery task name but move the current body into:

```python
async def run_character_asset_generation(character_id: str, job_id: str, *, session: AsyncSession | None = None) -> None:
    ...
```

The Celery wrapper keeps the existing task name. `gen_character_asset_single` is a `Job.kind`, not a Celery task name:

```python
@celery_app.task(name="ai.gen_character_asset", queue="ai", bind=True)
def gen_character_asset(self, character_id: str, job_id: str) -> None:
    asyncio.run(run_character_asset_generation(character_id, job_id))
```

Preserve existing parent-job aggregation logic if this file also updates the `gen_character_asset` parent job.

- [ ] **Step 4: Generate full-body and headshot images**

Inside `run_character_asset_generation`, after loading `project` and `character`:

```python
full_body_prompt = build_character_full_body_prompt(project, character)
headshot_prompt = build_character_headshot_prompt(project, character)
client = get_volcano_client()
model = get_settings().ark_image_model
references = [build_asset_url(project.character_style_reference_image_url)] if project.character_style_reference_image_url else None

await update_job_progress(session, job_id, status="running", progress=30, done=0, total=2)
if not character.full_body_image_url:
    full_body_resp = await client.image_generations(model, full_body_prompt, references=references, n=1, size="768x1344")
    full_body_temp_url = full_body_resp["data"][0]["url"]
    full_body_key = await persist_generated_asset(
        url=full_body_temp_url,
        project_id=project.id,
        kind="character_full_body",
        ext="png",
    )
    character.full_body_image_url = full_body_key
    character.reference_image_url = full_body_key
    await session.commit()
else:
    full_body_temp_url = build_asset_url(character.full_body_image_url)

await update_job_progress(session, job_id, status="running", progress=60, done=1, total=2)
headshot_references = [full_body_temp_url]
if references:
    headshot_references.extend(references)
headshot_resp = await client.image_generations(model, headshot_prompt, references=headshot_references, n=1, size="768x1344")
headshot_key = await persist_generated_asset(
    url=headshot_resp["data"][0]["url"],
    project_id=project.id,
    kind="character_headshot",
    ext="png",
)

character.headshot_image_url = headshot_key
await session.commit()
await update_job_progress(session, job_id, status="succeeded", progress=100, done=2, total=2)
```

This preserves the spec's partial-failure behavior: if the full-body image succeeds and headshot generation fails, the full-body image is already committed and retry can fill the missing headshot. User-triggered "重新生成" can clear both image fields before calling this runner when full regeneration is desired.

- [ ] **Step 5: Update character API response fallback**

In `backend/app/api/characters.py`, update `_to_character_out`:

```python
full_body_key = c.full_body_image_url or c.reference_image_url
return CharacterOut(
    ...
    reference_image_url=build_asset_url(full_body_key) if full_body_key else None,
    full_body_image_url=build_asset_url(full_body_key) if full_body_key else None,
    headshot_image_url=build_asset_url(c.headshot_image_url) if c.headshot_image_url else None,
)
```

- [ ] **Step 6: Run character generation tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_character_dual_image_generation.py tests/integration/test_style_reference_aggregate.py -v
```

Expected: tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/tasks/ai/gen_character_asset.py backend/app/api/characters.py backend/tests/integration/test_character_dual_image_generation.py
git commit -m "feat(backend): generate character full body and headshot assets"
```

---

## Task 6: Scene No-Person Generation and Reference Input

**Files:**

- Modify: `backend/app/tasks/ai/gen_scene_asset.py`
- Test: `backend/tests/integration/test_scene_no_person_generation.py`

- [ ] **Step 1: Write failing scene generation test**

Create `backend/tests/integration/test_scene_no_person_generation.py`:

```python
import pytest

from app.domain.models import Job, Project, ProjectStage, Scene
from app.infra.asset_store import build_asset_url
from app.tasks.ai.gen_scene_asset import run_scene_asset_generation


class FakeImageClient:
    def __init__(self):
        self.calls = []

    async def image_generations(self, model, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return {"data": [{"url": "https://example.test/scene.png"}]}


@pytest.mark.asyncio
async def test_scene_asset_generation_forbids_people_and_uses_style_reference(db_session, monkeypatch):
    client = FakeImageClient()
    monkeypatch.setattr("app.tasks.ai.gen_scene_asset.get_volcano_client", lambda: client)
    async def fake_persist_generated_asset(**kwargs):
        return "projects/p1/scenes/gate.png"

    monkeypatch.setattr("app.tasks.ai.gen_scene_asset.persist_generated_asset", fake_persist_generated_asset)

    project = Project(
        name="雨夜",
        novel_text="n",
        stage=ProjectStage.CHARACTERS_LOCKED,
        scene_style_reference_image_url="projects/p1/style/scene.png",
    )
    db_session.add(project)
    await db_session.flush()
    scene = Scene(project_id=project.id, name="朱雀门", theme="palace", summary="雨夜宫门")
    db_session.add(scene)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_scene_asset_single", status="queued", progress=10, done=0, total=1, target_id=scene.id, target_type="scene")
    db_session.add(job)
    await db_session.commit()

    await run_scene_asset_generation(scene.id, job.id, session=db_session)
    await db_session.refresh(scene)

    assert scene.reference_image_url == "projects/p1/scenes/gate.png"
    assert "绝对不出现人物" in client.calls[0]["prompt"]
    assert build_asset_url("projects/p1/style/scene.png") in client.calls[0]["references"]
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_scene_no_person_generation.py -v
```

Expected: fails because the task does not pass scene style reference URLs and the prompt is too weak.

- [ ] **Step 3: Refactor task to expose async runner**

In `backend/app/tasks/ai/gen_scene_asset.py`, keep the existing Celery task name but move the body into:

```python
async def run_scene_asset_generation(scene_id: str, job_id: str, *, session: AsyncSession | None = None) -> None:
    ...
```

The Celery wrapper keeps the existing task name. `gen_scene_asset_single` is a `Job.kind`, not a Celery task name:

```python
@celery_app.task(name="ai.gen_scene_asset", queue="ai", bind=True)
def gen_scene_asset(self, scene_id: str, job_id: str) -> None:
    asyncio.run(run_scene_asset_generation(scene_id, job_id))
```

- [ ] **Step 4: Pass scene style reference as provider reference**

Inside the scene runner:

```python
references = [build_asset_url(project.scene_style_reference_image_url)] if project.scene_style_reference_image_url else None
gen_resp = await client.image_generations(
    model,
    prompt,
    references=references,
    n=1,
    size="1344x768",
)
```

Keep `reference_image_url` as the only persisted scene asset field.

- [ ] **Step 5: Run scene tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_scene_no_person_generation.py tests/unit/test_visual_reference_prompts.py -v
```

Expected: tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/ai/gen_scene_asset.py backend/tests/integration/test_scene_no_person_generation.py
git commit -m "feat(backend): enforce no-person scene asset generation"
```

---

## Task 7: Reference Candidate Updates

**Files:**

- Modify: `backend/app/domain/services/reference_candidates.py`
- Modify: `backend/app/domain/services/shot_reference_service.py`
- Test: `backend/tests/integration/test_reference_candidates_dual_character_scene.py`

- [ ] **Step 1: Write failing reference candidate test**

Create `backend/tests/integration/test_reference_candidates_dual_character_scene.py`:

```python
import pytest

from app.domain.models import Character, Project, ProjectStage, Scene, StoryboardShot
from app.domain.services.shot_reference_service import ShotReferenceService


@pytest.mark.asyncio
async def test_candidates_include_character_full_body_headshot_and_scene_no_person(db_session):
    project = Project(name="雨夜", novel_text="n", stage=ProjectStage.SCENES_LOCKED)
    db_session.add(project)
    await db_session.flush()
    shot = StoryboardShot(project_id=project.id, idx=1, title="宫门雨夜", description="秦昭到宫门")
    character = Character(
        project_id=project.id,
        name="秦昭",
        role_type="protagonist",
        full_body_image_url="projects/p1/characters/qz-full.png",
        headshot_image_url="projects/p1/characters/qz-head.png",
    )
    scene = Scene(project_id=project.id, name="朱雀门", theme="palace", reference_image_url="projects/p1/scenes/gate.png")
    db_session.add_all([shot, character, scene])
    await db_session.commit()

    candidates = await ShotReferenceService(db_session).list_candidates(project.id, shot.id)
    keys = {item["mention_key"] for item in candidates}

    assert "character:" + character.id in keys
    assert "character_headshot:" + character.id in keys
    assert "scene:" + scene.id in keys
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_reference_candidates_dual_character_scene.py -v
```

Expected: fails because candidates include only one character image.

- [ ] **Step 3: Emit dual character candidates**

In `backend/app/domain/services/reference_candidates.py`, when mapping characters, keep the existing `character:{id}` key as the full-body compatibility candidate and emit a second headshot candidate when available:

```python
if char.full_body_image_url or char.reference_image_url:
    key = char.full_body_image_url or char.reference_image_url
    items.append(
        {
            "id": f"character:{char.id}",
            "mention_key": f"character:{char.id}",
            "kind": "character",
            "source_id": char.id,
            "origin": "auto",
            "name": char.name,
            "alias": f"{char.name}-全身",
            "image_url": build_asset_url(key),
            "reason": _character_reason(shot_text, shot_terms, char),
        }
    )
if char.headshot_image_url:
    items.append(
        {
            "id": f"character_headshot:{char.id}",
            "mention_key": f"character_headshot:{char.id}",
            "kind": "character_headshot",
            "source_id": char.id,
            "origin": "auto",
            "name": char.name,
            "alias": f"{char.name}-头像",
            "image_url": build_asset_url(char.headshot_image_url),
            "reason": "角色白底头像参考图",
        }
    )
```

Keep the scene candidate kind as `scene`, set `reason` to include `"无人场景参考图"` when there is no stronger scene match reason, and keep `mention_key=f"scene:{scene.id}"`.

Also update helper filters in `backend/app/domain/services/reference_candidates.py`:

```python
CHARACTER_REFERENCE_KINDS = {"character", "character_headshot"}


def default_selected_references(candidates: list[dict]) -> list[dict]:
    scenes = [item for item in candidates if item.get("kind") == "scene"]
    characters = [item for item in candidates if item.get("kind") in CHARACTER_REFERENCE_KINDS]
    return [*scenes[:1], *characters[:2]]
```

In `selected_references_from_ids`, count both `character` and `character_headshot` in the same character lane:

```python
lane = "character" if kind in CHARACTER_REFERENCE_KINDS else kind
if lane == "scene" and selected_kinds["scene"] >= 1:
    continue
if lane == "character" and selected_kinds["character"] >= 2:
    continue

selected.append(candidate)
if lane in selected_kinds:
    selected_kinds[lane] += 1
```

This preserves old persisted prompt mentions using `character:{id}` while adding a new selectable headshot reference.

- [ ] **Step 4: Run reference candidate test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_reference_candidates_dual_character_scene.py -v
```

Expected: test passes.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/services/reference_candidates.py backend/app/domain/services/shot_reference_service.py backend/tests/integration/test_reference_candidates_dual_character_scene.py
git commit -m "feat(backend): expose dual character reference candidates"
```

---

## Task 8: Frontend Types, API Wrapper, and Store Orchestration

**Files:**

- Create: `frontend/src/api/styleReferences.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/store/workbench.ts`
- Test: `frontend/tests/unit/workbench.style-reference.spec.ts`

- [ ] **Step 1: Write failing store test**

Create `frontend/tests/unit/workbench.style-reference.spec.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useWorkbenchStore } from '@/store/workbench'
import { styleReferencesApi } from '@/api/styleReferences'

describe('workbench style references', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts character style reference job', async () => {
    vi.spyOn(styleReferencesApi, 'generateStyleReference').mockResolvedValue({ job_id: 'job-character' })
    const store = useWorkbenchStore()
    store.current = { id: 'project-1', stage_raw: 'storyboard_ready' } as never

    await store.generateStyleReference('character')

    expect(styleReferencesApi.generateStyleReference).toHaveBeenCalledWith('project-1', 'character')
    expect(store.activeCharacterStyleReferenceJobId).toBe('job-character')
  })

  it('starts scene style reference job', async () => {
    vi.spyOn(styleReferencesApi, 'generateStyleReference').mockResolvedValue({ job_id: 'job-scene' })
    const store = useWorkbenchStore()
    store.current = { id: 'project-1', stage_raw: 'characters_locked' } as never

    await store.generateStyleReference('scene')

    expect(styleReferencesApi.generateStyleReference).toHaveBeenCalledWith('project-1', 'scene')
    expect(store.activeSceneStyleReferenceJobId).toBe('job-scene')
  })
})
```

- [ ] **Step 2: Run frontend test and verify it fails**

Run:

```bash
cd frontend
npm run test -- tests/unit/workbench.style-reference.spec.ts
```

Expected: fails because the API wrapper and store action do not exist.

- [ ] **Step 3: Add frontend types**

In `frontend/src/types/index.ts`, add:

```ts
export type StyleReferenceKind = 'character' | 'scene'
export type StyleReferenceStatus = 'empty' | 'running' | 'succeeded' | 'failed'

export interface StyleReferenceState {
  imageUrl: string | null
  prompt: string | null
  status: StyleReferenceStatus
  error: string | null
}
```

Add to `ProjectData`:

```ts
characterStyleReference: StyleReferenceState
sceneStyleReference: StyleReferenceState
```

Add to `CharacterAsset`:

```ts
full_body_image_url?: string | null
headshot_image_url?: string | null
```

Mirror the API payload fields in `frontend/src/types/api.ts`.

- [ ] **Step 4: Add API wrapper**

Create `frontend/src/api/styleReferences.ts`:

```ts
import { client } from './client'
import type { StyleReferenceKind } from '@/types'

export interface StyleReferenceJobAck {
  job_id: string
}

export const styleReferencesApi = {
  async generateStyleReference(projectId: string, kind: StyleReferenceKind): Promise<StyleReferenceJobAck> {
    const path =
      kind === 'character'
        ? `/projects/${projectId}/character-style-reference/generate`
        : `/projects/${projectId}/scene-style-reference/generate`
    const response = await client.post(path)
    return response.data as StyleReferenceJobAck
  },
}
```

The existing Axios interceptor unwraps the API envelope, so `response.data` is already the `StyleReferenceJobAck`.

- [ ] **Step 5: Update store**

In `frontend/src/store/workbench.ts`, follow the existing setup-store pattern. Add refs next to the prompt profile job refs:

```ts
import { styleReferencesApi } from "@/api/styleReferences";
import type { StyleReferenceKind } from "@/types";
```

```ts
const characterStyleReferenceJob = ref<{ projectId: string; jobId: string } | null>(null);
const characterStyleReferenceError = ref<string | null>(null);
const sceneStyleReferenceJob = ref<{ projectId: string; jobId: string } | null>(null);
const sceneStyleReferenceError = ref<string | null>(null);
```

Add computed active IDs next to the existing prompt profile computed values:

```ts
const activeCharacterStyleReferenceJobId = computed<string | null>(() =>
  scopedJobId(characterStyleReferenceJob.value)
);
const activeSceneStyleReferenceJobId = computed<string | null>(() =>
  scopedJobId(sceneStyleReferenceJob.value)
);
```

Add helper functions:

```ts
function styleReferenceJobRef(kind: StyleReferenceKind) {
  return kind === "character" ? characterStyleReferenceJob : sceneStyleReferenceJob;
}

function styleReferenceErrorRef(kind: StyleReferenceKind) {
  return kind === "character" ? characterStyleReferenceError : sceneStyleReferenceError;
}
```

Add action:

```ts
async generateStyleReference(kind: StyleReferenceKind) {
  if (!current.value) throw new Error("generateStyleReference: no current project");
  styleReferenceErrorRef(kind).value = null;
  const ack = await styleReferencesApi.generateStyleReference(current.value.id, kind);
  styleReferenceJobRef(kind).value = { projectId: current.value.id, jobId: ack.job_id };
  return ack.job_id;
}
```

Add completion helpers for the panels' `useJobPolling` callbacks:

```ts
function markStyleReferenceJobSucceeded(kind: StyleReferenceKind) {
  styleReferenceJobRef(kind).value = null;
  styleReferenceErrorRef(kind).value = null;
}

function markStyleReferenceJobFailed(kind: StyleReferenceKind, msg: string) {
  styleReferenceJobRef(kind).value = null;
  styleReferenceErrorRef(kind).value = msg;
}
```

In `findAndTrackActiveJobs()`, recover running and failed jobs from `projectsApi.getJobs()` just like prompt profile jobs:

```ts
if (stage === "storyboard_ready") {
  const styleJob = running("gen_character_style_reference");
  if (styleJob) {
    characterStyleReferenceJob.value = { projectId: current.value.id, jobId: styleJob.id };
  } else {
    const failed = lastFailed("gen_character_style_reference");
    characterStyleReferenceError.value = failed?.error_msg ?? null;
  }
} else {
  characterStyleReferenceJob.value = null;
}

if (stage === "characters_locked") {
  const styleJob = running("gen_scene_style_reference");
  if (styleJob) {
    sceneStyleReferenceJob.value = { projectId: current.value.id, jobId: styleJob.id };
  } else {
    const failed = lastFailed("gen_scene_style_reference");
    sceneStyleReferenceError.value = failed?.error_msg ?? null;
  }
} else {
  sceneStyleReferenceJob.value = null;
}
```

Return the new refs, computed values, and actions from the setup store.

- [ ] **Step 6: Run store test**

Run:

```bash
cd frontend
npm run test -- tests/unit/workbench.style-reference.spec.ts
```

Expected: tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/styleReferences.ts frontend/src/types/api.ts frontend/src/types/index.ts frontend/src/store/workbench.ts frontend/tests/unit/workbench.style-reference.spec.ts
git commit -m "feat(frontend): add style reference store orchestration"
```

---

## Task 9: Frontend Style Reference Card and Panel Layouts

**Files:**

- Create: `frontend/src/components/common/StyleReferenceCard.vue`
- Modify: `frontend/src/components/character/CharacterAssetsPanel.vue`
- Modify: `frontend/src/components/scene/SceneAssetsPanel.vue`
- Test: `frontend/tests/unit/style-reference-card.spec.ts`
- Test: `frontend/tests/unit/character-scene-style-reference-layout.spec.ts`

- [ ] **Step 1: Write failing card test**

Create `frontend/tests/unit/style-reference-card.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import StyleReferenceCard from '@/components/common/StyleReferenceCard.vue'

describe('StyleReferenceCard', () => {
  it('renders empty character reference state', () => {
    const wrapper = mount(StyleReferenceCard, {
      props: {
        kind: 'character',
        state: { imageUrl: null, prompt: null, status: 'empty', error: null },
        disabled: false,
        running: false,
      },
    })

    expect(wrapper.text()).toContain('统一角色形象参考图')
    expect(wrapper.text()).toContain('生成参考图')
  })

  it('emits generate when action is clicked', async () => {
    const wrapper = mount(StyleReferenceCard, {
      props: {
        kind: 'scene',
        state: { imageUrl: null, prompt: null, status: 'empty', error: null },
        disabled: false,
        running: false,
      },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('generate')).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Run card test and verify it fails**

Run:

```bash
cd frontend
npm run test -- tests/unit/style-reference-card.spec.ts
```

Expected: fails because the component does not exist.

- [ ] **Step 3: Implement card component**

Create `frontend/src/components/common/StyleReferenceCard.vue`:

```vue
<template>
  <section class="style-reference-card">
    <header class="style-reference-card__header">
      <div>
        <p class="style-reference-card__eyebrow">{{ eyebrow }}</p>
        <h3>{{ title }}</h3>
      </div>
      <button type="button" :disabled="disabled || running" @click="$emit('generate')">
        {{ actionLabel }}
      </button>
    </header>

    <div class="style-reference-card__preview" :class="{ 'is-empty': !state.imageUrl }">
      <img v-if="state.imageUrl" :src="state.imageUrl" :alt="title" />
      <div v-else class="style-reference-card__placeholder">{{ placeholder }}</div>
    </div>

    <div v-if="running || state.status === 'running'" class="style-reference-card__progress">
      <span>正在生成...</span>
      <div class="style-reference-card__bar"><i /></div>
    </div>
    <p v-if="state.error" class="style-reference-card__error">{{ state.error }}</p>
    <p class="style-reference-card__hint">{{ hint }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StyleReferenceKind, StyleReferenceState } from '@/types'

const props = defineProps<{
  kind: StyleReferenceKind
  state: StyleReferenceState
  disabled: boolean
  running: boolean
}>()

defineEmits<{ generate: [] }>()

const title = computed(() => (props.kind === 'character' ? '统一角色形象参考图' : '统一场景视觉参考图'))
const eyebrow = computed(() => (props.kind === 'character' ? 'Character Style' : 'Scene Style'))
const placeholder = computed(() => (props.kind === 'character' ? '白底正面全身形象' : '无人物场景视觉'))
const hint = computed(() =>
  props.kind === 'character'
    ? '用于统一人物比例、画风、服装质感和白底全身形象。'
    : '用于统一空间结构、色彩光影、建筑材质和时代氛围；画面中不允许出现人物。',
)
const actionLabel = computed(() => (props.state.imageUrl ? '重新生成' : props.state.status === 'failed' ? '重试' : '生成参考图'))
</script>
```

Add scoped CSS using existing dark tokens. Keep borders and background aligned with `PromptProfileCard`.

- [ ] **Step 4: Add panel layout tests**

Create `frontend/tests/unit/character-scene-style-reference-layout.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import CharacterAssetsPanel from '@/components/character/CharacterAssetsPanel.vue'
import SceneAssetsPanel from '@/components/scene/SceneAssetsPanel.vue'
import { useWorkbenchStore } from '@/store/workbench'

describe('style reference layout', () => {
  it('renders character style reference next to character profile', () => {
    setActivePinia(createPinia())
    const store = useWorkbenchStore()
    store.current = {
      id: 'p1',
      stage_raw: 'storyboard_ready',
      characterPromptProfile: { draft: null, applied: null, status: 'empty' },
      characterStyleReference: { imageUrl: null, prompt: null, status: 'empty', error: null },
      characters: [],
      scenes: [],
      storyboards: [],
    } as never
    vi.spyOn(store, 'generateStyleReference').mockResolvedValue('job-style')
    const wrapper = mount(CharacterAssetsPanel, { global: { stubs: ['PromptProfileCard', 'StyleReferenceCard', 'StageRollbackModal'] } })
    expect(wrapper.text()).toContain('统一角色形象参考图')
  })

  it('renders scene style reference next to scene profile', () => {
    setActivePinia(createPinia())
    const store = useWorkbenchStore()
    store.current = {
      id: 'p1',
      stage_raw: 'characters_locked',
      scenePromptProfile: { draft: null, applied: null, status: 'empty' },
      sceneStyleReference: { imageUrl: null, prompt: null, status: 'empty', error: null },
      characters: [],
      scenes: [],
      storyboards: [],
    } as never
    vi.spyOn(store, 'generateStyleReference').mockResolvedValue('job-style')
    const wrapper = mount(SceneAssetsPanel, { global: { stubs: ['PromptProfileCard', 'StyleReferenceCard', 'StageRollbackModal'] } })
    expect(wrapper.text()).toContain('统一场景视觉参考图')
  })
})
```

These panels read from the real workbench setup store; the test sets `store.current` directly and does not pass unsupported props.

- [ ] **Step 5: Wire character panel**

In `frontend/src/components/character/CharacterAssetsPanel.vue`, wrap the existing `PromptProfileCard` and the new card:

```vue
<div class="profile-reference-layout">
  <PromptProfileCard ... />
  <StyleReferenceCard
    kind="character"
    :state="characterStyleReference"
    :disabled="!flags.canEditCharacters"
    :running="!!activeCharacterStyleReferenceJobId"
    @generate="handleGenerateStyleReference"
  />
</div>
```

Add these script bindings:

```ts
const {
  activeCharacterStyleReferenceJobId,
  characterStyleReferenceError,
} = storeToRefs(store);

const characterStyleReference = computed(
  () => current.value?.characterStyleReference ?? { imageUrl: null, prompt: null, status: "empty" as const, error: null }
);

async function handleGenerateStyleReference() {
  if (!flags.value.canEditCharacters) {
    warnCharacterStageGate("当前阶段不能生成角色风格母版");
    return;
  }
  await store.generateStyleReference("character");
}
```

- [ ] **Step 6: Wire scene panel**

In `frontend/src/components/scene/SceneAssetsPanel.vue`, wrap the existing `PromptProfileCard` and the new card:

```vue
<div class="profile-reference-layout">
  <PromptProfileCard ... />
  <StyleReferenceCard
    kind="scene"
    :state="sceneStyleReference"
    :disabled="!flags.canEditScenes"
    :running="!!activeSceneStyleReferenceJobId"
    @generate="handleGenerateStyleReference"
  />
</div>
```

Use the current `flags.canEditCharacters` and `flags.canEditScenes` values from the existing panel logic.

Add these script bindings:

```ts
const {
  activeSceneStyleReferenceJobId,
  sceneStyleReferenceError,
} = storeToRefs(store);

const sceneStyleReference = computed(
  () => current.value?.sceneStyleReference ?? { imageUrl: null, prompt: null, status: "empty" as const, error: null }
);

async function handleGenerateStyleReference() {
  if (!flags.value.canEditScenes) {
    warnSceneStageGate("当前阶段不能生成场景风格母版");
    return;
  }
  await store.generateStyleReference("scene");
}
```

- [ ] **Step 7: Add shared layout CSS**

In the relevant component scoped styles:

```css
.profile-reference-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.8fr);
  gap: 18px;
  align-items: start;
}

@media (max-width: 1100px) {
  .profile-reference-layout {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 8: Run frontend tests**

Run:

```bash
cd frontend
npm run test -- tests/unit/style-reference-card.spec.ts tests/unit/character-scene-style-reference-layout.spec.ts
```

Expected: tests pass.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/common/StyleReferenceCard.vue frontend/src/components/character/CharacterAssetsPanel.vue frontend/src/components/scene/SceneAssetsPanel.vue frontend/tests/unit/style-reference-card.spec.ts frontend/tests/unit/character-scene-style-reference-layout.spec.ts
git commit -m "feat(frontend): add project style reference cards"
```

---

## Task 10: Character Dual-Image UI and Scene No-Person Labeling

**Files:**

- Modify: `frontend/src/components/character/CharacterAssetsPanel.vue`
- Modify: `frontend/src/components/scene/SceneAssetsPanel.vue`
- Test: `frontend/tests/unit/character-dual-image-ui.spec.ts`
- Test: `frontend/tests/unit/scene-no-person-ui.spec.ts`

- [ ] **Step 1: Write failing UI tests**

Create `frontend/tests/unit/character-dual-image-ui.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import CharacterAssetsPanel from '@/components/character/CharacterAssetsPanel.vue'
import { useWorkbenchStore } from '@/store/workbench'

describe('character dual image UI', () => {
  it('shows full body and headshot labels when selected character has both images', () => {
    setActivePinia(createPinia())
    const store = useWorkbenchStore()
    store.current = {
      id: 'p1',
      stage_raw: 'storyboard_ready',
      characterPromptProfile: { draft: null, applied: null, status: 'empty' },
      characters: [
        {
          id: 'c1',
          name: '秦昭',
          role_type: 'supporting',
          role: '配角',
          is_protagonist: false,
          locked: false,
          summary: '少年天子',
          description: '黑金冕服',
          meta: [],
          reference_image_url: 'full.png',
          full_body_image_url: 'full.png',
          headshot_image_url: 'head.png',
        },
      ],
      scenes: [],
      storyboards: [],
    } as never
    store.selectedCharacterId = 'c1'

    const wrapper = mount(CharacterAssetsPanel, {
      global: { stubs: ['PromptProfileCard', 'StyleReferenceCard', 'StageRollbackModal'] },
    })

    expect(wrapper.text()).toContain('全身参考图')
    expect(wrapper.text()).toContain('头像参考图')
  })
})
```

Create `frontend/tests/unit/scene-no-person-ui.spec.ts`:

```ts
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import SceneAssetsPanel from '@/components/scene/SceneAssetsPanel.vue'
import { useWorkbenchStore } from '@/store/workbench'

describe('scene no-person UI', () => {
  it('labels generated scene image as no-person reference', () => {
    setActivePinia(createPinia())
    const store = useWorkbenchStore()
    store.current = {
      id: 'p1',
      stage_raw: 'characters_locked',
      scenePromptProfile: { draft: null, applied: null, status: 'empty' },
      characters: [],
      scenes: [
        {
          id: 's1',
          name: '朱雀门',
          theme: 'palace',
          summary: '雨夜宫门',
          description: '无人宫门',
          meta: [],
          locked: false,
          template_id: null,
          reference_image_url: 'scene.png',
          usage: '',
        },
      ],
      storyboards: [],
    } as never
    store.selectedSceneId = 's1'

    const wrapper = mount(SceneAssetsPanel, {
      global: { stubs: ['PromptProfileCard', 'StyleReferenceCard', 'StageRollbackModal'] },
    })

    expect(wrapper.text()).toContain('无人场景参考图')
  })
})
```

These tests use the real setup store shape instead of passing unsupported `characters` or `scenes` props into the panels.

- [ ] **Step 2: Run UI tests and verify they fail**

Run:

```bash
cd frontend
npm run test -- tests/unit/character-dual-image-ui.spec.ts tests/unit/scene-no-person-ui.spec.ts
```

Expected: tests fail because labels are missing.

- [ ] **Step 3: Implement character dual image display**

In `CharacterAssetsPanel.vue`, replace the selected-character single image block with:

```vue
<div class="character-image-pair">
  <figure class="asset-image-card">
    <img v-if="selectedCharacter.full_body_image_url || selectedCharacter.reference_image_url" :src="selectedCharacter.full_body_image_url || selectedCharacter.reference_image_url" alt="全身参考图" />
    <div v-else class="asset-image-card__empty">等待生成全身图</div>
    <figcaption>全身参考图</figcaption>
  </figure>
  <figure class="asset-image-card">
    <img v-if="selectedCharacter.headshot_image_url" :src="selectedCharacter.headshot_image_url" alt="头像参考图" />
    <div v-else class="asset-image-card__empty">等待生成头像图</div>
    <figcaption>头像参考图</figcaption>
  </figure>
</div>
```

Add responsive CSS:

```css
.character-image-pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

@media (max-width: 760px) {
  .character-image-pair {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 4: Implement scene no-person labeling**

In `SceneAssetsPanel.vue`, update the image heading or caption:

```vue
<h4>无人场景参考图</h4>
```

Add hint text near regenerate action:

```vue
<p class="asset-hint">只保留环境、建筑、道具、天气和光影；画面中不应出现人物。</p>
```

- [ ] **Step 5: Run UI tests**

Run:

```bash
cd frontend
npm run test -- tests/unit/character-dual-image-ui.spec.ts tests/unit/scene-no-person-ui.spec.ts
```

Expected: tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/character/CharacterAssetsPanel.vue frontend/src/components/scene/SceneAssetsPanel.vue frontend/tests/unit/character-dual-image-ui.spec.ts frontend/tests/unit/scene-no-person-ui.spec.ts
git commit -m "feat(frontend): show character dual images and no-person scenes"
```

---

## Task 11: End-to-End Verification

**Files:**

- Modify: `backend/README.md`
- Modify: `frontend/README.md`

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_style_reference_schema.py tests/unit/test_visual_reference_prompts.py tests/integration/test_style_reference_aggregate.py tests/integration/test_style_reference_api.py tests/integration/test_style_reference_tasks.py tests/integration/test_character_dual_image_generation.py tests/integration/test_scene_no_person_generation.py tests/integration/test_reference_candidates_dual_character_scene.py -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Run backend lint/type checks**

Run:

```bash
cd backend
./.venv/bin/ruff check app tests
./.venv/bin/mypy
```

Expected: both commands pass.

- [ ] **Step 3: Run frontend focused tests and typecheck**

Run:

```bash
cd frontend
npm run test -- tests/unit/workbench.style-reference.spec.ts tests/unit/style-reference-card.spec.ts tests/unit/character-scene-style-reference-layout.spec.ts tests/unit/character-dual-image-ui.spec.ts tests/unit/scene-no-person-ui.spec.ts
npm run typecheck
npm run lint
```

Expected: tests, typecheck, and lint pass.

- [ ] **Step 4: Start live stack for browser verification**

Run from repo root with the required dev terminal helper:

```bash
script/dev_terminal.sh open
script/dev_terminal.sh send "cd /Users/macbook/Documents/trae_projects/comic-drama-platform && script/start_all.sh"
script/dev_terminal.sh status
```

Expected: backend `:8000`, frontend `:5173`, Celery AI, and Celery video are running.

- [ ] **Step 5: Browser smoke**

In the in-app browser:

1. Open `http://localhost:5173`.
2. Open a project at `storyboard_ready`.
3. Navigate to 角色设定.
4. Confirm the top area shows 角色统一视觉设定 and 统一角色形象参考图 side by side.
5. Click 生成参考图 and confirm a running progress state appears.
6. Refresh the page and confirm the running job is still represented.
7. Complete or mock the job and confirm the image persists after refresh.
8. Generate or regenerate one character and confirm both 全身参考图 and 头像参考图 are shown.
9. Move to 场景设定 at `characters_locked`.
10. Generate scene style reference and confirm the prompt snapshot contains no-person constraints by querying the project detail API: `curl -fsS http://127.0.0.1:8000/api/v1/projects/<PROJECT_ID> | jq -r '.data.sceneStyleReference.prompt'`.
11. Generate or regenerate one scene and confirm UI labels it as 无人场景参考图.
12. Open shot reference picker and confirm candidates include `角色-全身`, `角色-头像`, and scene image candidates.

- [ ] **Step 6: Update README notes**

In `backend/README.md`, add a short implementation note under the M3 asset section:

```markdown
### Visual style references

Project-level character and scene style references are generated through async jobs:
`gen_character_style_reference` and `gen_scene_style_reference`. Character asset generation now writes
`full_body_image_url`, `headshot_image_url`, and keeps `reference_image_url` as a full-body compatibility alias.
Scene asset prompts must keep explicit no-person constraints.
```

In `frontend/README.md`, add:

```markdown
### Visual style reference UI

Character and scene setup pages render `StyleReferenceCard` next to `PromptProfileCard`.
Character detail views show full-body and headshot images; scene detail views label generated scene images as no-person references.
```

- [ ] **Step 7: Commit verification docs**

```bash
git add backend/README.md frontend/README.md
git commit -m "docs: document visual style reference workflow"
```

---

## Self-Review

Spec coverage:

- 角色设定页新增统一角色形象参考图: Task 8 and Task 9.
- 场景设定页新增统一场景视觉参考图: Task 8 and Task 9.
- 角色生成两张白底图: Task 1, Task 2, Task 5, Task 10.
- 场景生成不允许出现人: Task 4, Task 6, Task 10.
- 所有远程 AI 调用异步 job: Task 3 and Task 4.
- 结果保存并刷新恢复: Task 1, Task 2, Task 4, Task 8, Task 11.
- 后续镜头候选包含角色全身图、头像图、无人场景图: Task 7 and Task 11.
- 老数据兼容: Task 2, Task 5, and Task 7 preserve `reference_image_url` and `character:{id}` mentions.
- 阶段权限沿用角色/场景现有 gate: Task 3.

Placeholder scan:

- The plan contains no deferred task markers or unspecified task entries.
- Where repository helper names may differ, the plan gives the exact intended logic and the exact files to adjust.

Type consistency:

- Backend uses `character_style_reference_*`, `scene_style_reference_*`, `full_body_image_url`, `headshot_image_url`.
- Frontend aggregate uses `characterStyleReference`, `sceneStyleReference`, `full_body_image_url`, `headshot_image_url`.
- Job kinds are consistently `gen_character_style_reference` and `gen_scene_style_reference`.
- Celery task names remain `ai.gen_character_asset` and `ai.gen_scene_asset`; `gen_character_asset_single` and `gen_scene_asset_single` remain only `Job.kind` values.

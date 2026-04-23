# Project Prompt Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为项目新增角色/场景两套可选的统一背景提示词配置，支持“先生成/编辑草稿，再确认并触发具体资产生成”，且无配置时保持现有角色图/场景图生成行为不变。

**Architecture:** 后端以 `Project` 上的 `draft/applied` 双版本 JSON 字段承载 prompt profile，通过独立的 `prompt_profiles` router 暴露 `generate / patch / clear / confirm` 动作；具体角色图与场景图任务改为调用共享 prompt builder，只读取 `applied`。前端在角色/场景面板顶部新增统一背景提示词卡片，状态以 `GET /projects/{id}` 聚合快照为准，草稿生成和确认后续生成都继续复用现有 job polling 模式。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / Alembic / Celery / MySQL 8 / pytest / Vue 3.5 / TypeScript strict / Pinia / Axios / Vitest。

---

## References

- Spec: `docs/superpowers/specs/2026-04-23-project-prompt-profile-design.md`
- Backend baseline:
  - `backend/app/domain/models/project.py`
  - `backend/app/domain/schemas/project.py`
  - `backend/app/domain/services/aggregate_service.py`
  - `backend/app/api/characters.py`
  - `backend/app/api/scenes.py`
  - `backend/app/tasks/ai/gen_character_asset.py`
  - `backend/app/tasks/ai/gen_scene_asset.py`
- Frontend baseline:
  - `frontend/src/types/api.ts`
  - `frontend/src/types/index.ts`
  - `frontend/src/api/projects.ts`
  - `frontend/src/store/workbench.ts`
  - `frontend/src/components/character/CharacterAssetsPanel.vue`
  - `frontend/src/components/scene/SceneAssetsPanel.vue`

## Scope

**Includes:**

- `Project` 新增四个 prompt profile JSON 字段
- 项目聚合详情补齐 `characterPromptProfile` / `scenePromptProfile`
- 角色/场景 prompt profile 的 `generate / patch / clear / confirm` 接口
- 新增草稿生成 job 与批量重生成未锁定资产 job
- 角色图 / 场景图任务接入共享 prompt builder
- 前端 PromptProfileCard、API、store、面板接入与单测

**Excludes:**

- `render_shot` 镜头渲染 prompt 改造
- 新增 `project.stage`
- 复杂 prompt 结构编辑器（负向提示词、标签权重等）
- 自动重生成已锁定角色/场景

## Current Baseline Notes

- 角色图和场景图 prompt 仍写死在 `gen_character_asset.py` / `gen_scene_asset.py` 内，且没有项目级上下文注入点。
- `ProjectDetail` 聚合目前没有任何项目级 prompt profile 字段，前端刷新后无法恢复草稿/生效版本状态。
- 角色与场景生成都已经是异步 job；新增配置草稿生成必须延续这一模式，不能在 HTTP 线程里直接调远程 AI。
- `CharacterAssetsPanel.vue` 与 `SceneAssetsPanel.vue` 顶部已有可用视觉留白，适合作为统一背景提示词配置区，不需要引入新页面或新 stage。

## File Structure

**Create:**

```text
backend/alembic/versions/6f9f0c2d0d6b_add_project_prompt_profiles.py
backend/app/api/prompt_profiles.py
backend/app/domain/schemas/prompt_profile.py
backend/app/domain/services/prompt_profile_service.py
backend/app/tasks/ai/prompt_builders.py
backend/app/tasks/ai/gen_character_prompt_profile.py
backend/app/tasks/ai/gen_scene_prompt_profile.py
backend/app/tasks/ai/regen_character_assets_batch.py
backend/app/tasks/ai/regen_scene_assets_batch.py
backend/tests/integration/test_prompt_profile_api.py
backend/tests/unit/test_prompt_builders.py
frontend/src/api/promptProfiles.ts
frontend/src/components/common/PromptProfileCard.vue
frontend/tests/unit/prompt-profiles.api.spec.ts
frontend/tests/unit/prompt-profile-card.spec.ts
frontend/tests/unit/workbench.prompt-profiles.spec.ts
```

**Modify:**

```text
backend/app/main.py
backend/app/domain/models/project.py
backend/app/domain/models/job.py
backend/app/domain/schemas/project.py
backend/app/domain/schemas/__init__.py
backend/app/domain/services/aggregate_service.py
backend/app/tasks/ai/__init__.py
backend/app/tasks/ai/gen_character_asset.py
backend/app/tasks/ai/gen_scene_asset.py
frontend/src/types/api.ts
frontend/src/types/index.ts
frontend/src/store/workbench.ts
frontend/src/components/character/CharacterAssetsPanel.vue
frontend/src/components/scene/SceneAssetsPanel.vue
frontend/src/utils/error.ts
frontend/README.md
backend/README.md
```

## Task 1: Project 持久化与聚合详情 contract

**Files:**
- Create: `backend/alembic/versions/6f9f0c2d0d6b_add_project_prompt_profiles.py`
- Modify: `backend/app/domain/models/project.py`
- Modify: `backend/app/domain/schemas/project.py`
- Modify: `backend/app/domain/schemas/__init__.py`
- Modify: `backend/app/domain/services/aggregate_service.py`
- Test: `backend/tests/integration/test_prompt_profile_api.py`

- [ ] **Step 1: 先写项目聚合详情的 failing 测试**

在 `backend/tests/integration/test_prompt_profile_api.py` 先写：

```python
@pytest.mark.asyncio
async def test_project_detail_returns_prompt_profile_statuses(client, db_session):
    project = Project(
        name="P1",
        stage="storyboard_ready",
        story="story",
        character_prompt_profile_draft={"prompt": "雨夜宫廷", "source": "ai"},
        character_prompt_profile_applied={"prompt": "雨夜宫廷", "source": "ai"},
        scene_prompt_profile_draft={"prompt": "冷青皇城", "source": "manual"},
        scene_prompt_profile_applied={"prompt": "旧版皇城", "source": "ai"},
    )
    db_session.add(project)
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{project.id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["characterPromptProfile"]["status"] == "applied"
    assert data["scenePromptProfile"]["status"] == "dirty"
```

- [ ] **Step 2: 运行测试确认 schema 尚未就位**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_prompt_profile_api.py::test_project_detail_returns_prompt_profile_statuses -v
```

Expected: FAIL，报 `Project` 无字段或返回缺少 `characterPromptProfile`。

- [ ] **Step 3: 扩展 Project 模型与 Alembic**

在 `backend/app/domain/models/project.py` 增加：

```python
    character_prompt_profile_draft: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    character_prompt_profile_applied: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scene_prompt_profile_draft: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scene_prompt_profile_applied: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

在 `backend/alembic/versions/6f9f0c2d0d6b_add_project_prompt_profiles.py` 写 migration：

```python
def upgrade() -> None:
    op.add_column("projects", sa.Column("character_prompt_profile_draft", sa.JSON(), nullable=True))
    op.add_column("projects", sa.Column("character_prompt_profile_applied", sa.JSON(), nullable=True))
    op.add_column("projects", sa.Column("scene_prompt_profile_draft", sa.JSON(), nullable=True))
    op.add_column("projects", sa.Column("scene_prompt_profile_applied", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "scene_prompt_profile_applied")
    op.drop_column("projects", "scene_prompt_profile_draft")
    op.drop_column("projects", "character_prompt_profile_applied")
    op.drop_column("projects", "character_prompt_profile_draft")
```

- [ ] **Step 4: 增加 prompt profile schema 与聚合输出**

在 `backend/app/domain/schemas/project.py` 增加：

```python
class PromptProfilePayload(BaseModel):
    prompt: str
    source: Literal["ai", "manual"]


class PromptProfileState(BaseModel):
    draft: PromptProfilePayload | None = None
    applied: PromptProfilePayload | None = None
    status: Literal["empty", "draft_only", "applied", "dirty"] = "empty"
```

并把 `ProjectDetail` 扩展为：

```python
    characterPromptProfile: PromptProfileState = PromptProfileState()
    scenePromptProfile: PromptProfileState = PromptProfileState()
```

在 `backend/app/domain/services/aggregate_service.py` 新增派生函数：

```python
def _profile_state(draft: dict | None, applied: dict | None) -> dict:
    if not draft and not applied:
        return {"draft": None, "applied": None, "status": "empty"}
    if draft and not applied:
        return {"draft": draft, "applied": None, "status": "draft_only"}
    if draft == applied:
        return {"draft": draft, "applied": applied, "status": "applied"}
    return {"draft": draft, "applied": applied, "status": "dirty"}
```

并在 `ProjectDetail(...)` 中填充：

```python
            characterPromptProfile=_profile_state(
                project.character_prompt_profile_draft,
                project.character_prompt_profile_applied,
            ),
            scenePromptProfile=_profile_state(
                project.scene_prompt_profile_draft,
                project.scene_prompt_profile_applied,
            ),
```

- [ ] **Step 5: 运行测试确认聚合 contract 通过**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_prompt_profile_api.py::test_project_detail_returns_prompt_profile_statuses -v
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/6f9f0c2d0d6b_add_project_prompt_profiles.py \
  backend/app/domain/models/project.py \
  backend/app/domain/schemas/project.py \
  backend/app/domain/schemas/__init__.py \
  backend/app/domain/services/aggregate_service.py \
  backend/tests/integration/test_prompt_profile_api.py
git commit -m "feat(backend): add project prompt profile persistence"
```

## Task 2: 草稿保存/清空 API 与阶段门禁

**Files:**
- Create: `backend/app/api/prompt_profiles.py`
- Create: `backend/app/domain/schemas/prompt_profile.py`
- Create: `backend/app/domain/services/prompt_profile_service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_prompt_profile_api.py`

- [ ] **Step 1: 先写 PATCH / DELETE 的 failing 测试**

在 `backend/tests/integration/test_prompt_profile_api.py` 追加：

```python
@pytest.mark.asyncio
async def test_patch_character_prompt_profile_saves_draft(client, db_session):
    project = await seed_project(db_session, stage="storyboard_ready")

    resp = await client.patch(
        f"/api/v1/projects/{project.id}/prompt-profiles/character",
        json={"prompt": "统一冷雨古风宫廷"},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["draft"]["prompt"] == "统一冷雨古风宫廷"
    assert data["draft"]["source"] == "manual"
    assert data["status"] == "draft_only"


@pytest.mark.asyncio
async def test_delete_scene_prompt_profile_draft_clears_draft_only(client, db_session):
    project = await seed_project(
        db_session,
        stage="characters_locked",
        scene_prompt_profile_draft={"prompt": "新稿", "source": "manual"},
        scene_prompt_profile_applied={"prompt": "旧稿", "source": "ai"},
    )

    resp = await client.delete(f"/api/v1/projects/{project.id}/prompt-profiles/scene/draft")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["draft"] is None
    assert data["applied"]["prompt"] == "旧稿"
    assert data["status"] == "applied"
```

- [ ] **Step 2: 运行测试确认 router 尚未存在**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_prompt_profile_api.py -k "patch_character_prompt_profile or delete_scene_prompt_profile" -v
```

Expected: FAIL with `404`。

- [ ] **Step 3: 定义独立 schema 与 service**

在 `backend/app/domain/schemas/prompt_profile.py` 创建：

```python
class PromptProfileDraftUpdate(BaseModel):
    prompt: str = Field(..., min_length=1)

    @field_validator("prompt")
    @classmethod
    def _strip_and_reject_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt 不能为空白")
        return value
```

在 `backend/app/domain/services/prompt_profile_service.py` 创建：

```python
class PromptProfileService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def update_draft(self, project: Project, kind: Literal["character", "scene"], prompt: str) -> dict:
        payload = {"prompt": prompt.strip(), "source": "manual"}
        if kind == "character":
            project.character_prompt_profile_draft = payload
            return _profile_state(project.character_prompt_profile_draft, project.character_prompt_profile_applied)
        project.scene_prompt_profile_draft = payload
        return _profile_state(project.scene_prompt_profile_draft, project.scene_prompt_profile_applied)

    async def clear_draft(self, project: Project, kind: Literal["character", "scene"]) -> dict:
        if kind == "character":
            project.character_prompt_profile_draft = None
            return _profile_state(project.character_prompt_profile_draft, project.character_prompt_profile_applied)
        project.scene_prompt_profile_draft = None
        return _profile_state(project.scene_prompt_profile_draft, project.scene_prompt_profile_applied)
```

- [ ] **Step 4: 暴露 PATCH / DELETE 并复用现有阶段门禁**

在 `backend/app/api/prompt_profiles.py` 创建 router：

```python
router = APIRouter(prefix="/projects/{project_id}/prompt-profiles", tags=["prompt-profiles"])


def _assert_profile_editable(project: Project, kind: Literal["character", "scene"]) -> None:
    try:
        assert_asset_editable(project, kind)
    except InvalidTransition as exc:
        raise ApiError(40301, str(exc), http_status=403) from exc


@router.patch("/{kind}")
async def patch_prompt_profile(...):
    ...
    _assert_profile_editable(project, kind)
    state = await svc.update_draft(project, kind, payload.prompt)
    await db.commit()
    return ok(state)


@router.delete("/{kind}/draft")
async def clear_prompt_profile_draft(...):
    ...
    _assert_profile_editable(project, kind)
    state = await svc.clear_draft(project, kind)
    await db.commit()
    return ok(state)
```

并在 `backend/app/main.py` 注册：

```python
from app.api import ..., prompt_profiles
...
app.include_router(prompt_profiles.router, prefix="/api/v1")
```

- [ ] **Step 5: 修正 clear draft 后的状态派生**

把 Task 1 的 `_profile_state()` 改成：

```python
    if not draft and applied:
        return {"draft": None, "applied": applied, "status": "applied"}
```

这样“清空草稿但保留已应用版本”不会被错误标成 `empty`。

- [ ] **Step 6: 运行测试确认 PATCH / DELETE 与 403 门禁通过**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_prompt_profile_api.py -k "patch_character_prompt_profile or delete_scene_prompt_profile" -v
```

Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/prompt_profiles.py \
  backend/app/domain/schemas/prompt_profile.py \
  backend/app/domain/services/prompt_profile_service.py \
  backend/app/main.py \
  backend/app/domain/schemas/project.py \
  backend/tests/integration/test_prompt_profile_api.py
git commit -m "feat(backend): add prompt profile draft APIs"
```

## Task 3: AI 生成角色/场景 prompt 草稿 job

**Files:**
- Create: `backend/app/tasks/ai/gen_character_prompt_profile.py`
- Create: `backend/app/tasks/ai/gen_scene_prompt_profile.py`
- Modify: `backend/app/tasks/ai/__init__.py`
- Modify: `backend/app/domain/models/job.py`
- Modify: `backend/app/api/prompt_profiles.py`
- Test: `backend/tests/integration/test_prompt_profile_api.py`

- [ ] **Step 1: 先写 generate ack 的 failing 测试**

在 `backend/tests/integration/test_prompt_profile_api.py` 追加：

```python
@pytest.mark.asyncio
async def test_generate_character_prompt_profile_returns_job_ack(client, db_session, monkeypatch):
    project = await seed_project(db_session, stage="storyboard_ready")

    dispatched: dict[str, str] = {}

    def fake_delay(project_id: str, job_id: str) -> None:
        dispatched["project_id"] = project_id
        dispatched["job_id"] = job_id

    monkeypatch.setattr(
        "app.api.prompt_profiles.gen_character_prompt_profile.delay",
        fake_delay,
    )

    resp = await client.post(f"/api/v1/projects/{project.id}/prompt-profiles/character/generate")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["job_id"] == dispatched["job_id"]
```

- [ ] **Step 2: 运行测试确认 generate endpoint 缺失**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_prompt_profile_api.py::test_generate_character_prompt_profile_returns_job_ack -v
```

Expected: FAIL with `404`。

- [ ] **Step 3: 扩展 job kind 并实现两个草稿生成任务**

在 `backend/app/domain/models/job.py` 的 `JOB_KIND_VALUES` 中追加：

```python
    "gen_character_prompt_profile",
    "gen_scene_prompt_profile",
    "regen_character_assets_batch",
    "regen_scene_assets_batch",
```

创建 `backend/app/tasks/ai/gen_character_prompt_profile.py`：

```python
async def _run(project_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await update_job_progress(session, job_id, status="running", progress=10)
        project = await session.get(Project, project_id)
        prompt = (
            "你是漫剧视觉设计师。请基于项目故事概述、角色列表和整体氛围，"
            "生成一段适合所有角色参考图复用的统一背景提示词。"
        )
        content = await get_volcano_client().chat_completions(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        payload = {"prompt": extract_json(content)["prompt"].strip(), "source": "ai"}
        project.character_prompt_profile_draft = payload
        await update_job_progress(session, job_id, status="succeeded", progress=100, result={"profile_kind": "character"})
        await session.commit()
```

场景任务同理，只改写 `scene_prompt_profile_draft`。

- [ ] **Step 4: 暴露 generate 端点**

在 `backend/app/api/prompt_profiles.py` 增加：

```python
@router.post("/{kind}/generate", response_model=Envelope[GenerateJobAck])
async def generate_prompt_profile(...):
    ...
    job = Job(project_id=project_id, kind=f"gen_{kind}_prompt_profile", status="queued", progress=0, done=0, total=None)
    db.add(job)
    await db.commit()
    if kind == "character":
        gen_character_prompt_profile.delay(project_id, job.id)
    else:
        gen_scene_prompt_profile.delay(project_id, job.id)
    return Envelope.success(GenerateJobAck(job_id=job.id, sub_job_ids=[]))
```

- [ ] **Step 5: 运行测试确认生成 job ack 正常**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_prompt_profile_api.py::test_generate_character_prompt_profile_returns_job_ack -v
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/ai/gen_character_prompt_profile.py \
  backend/app/tasks/ai/gen_scene_prompt_profile.py \
  backend/app/tasks/ai/__init__.py \
  backend/app/domain/models/job.py \
  backend/app/api/prompt_profiles.py \
  backend/tests/integration/test_prompt_profile_api.py
git commit -m "feat(backend): add prompt profile generation jobs"
```

## Task 4: confirm、批量重生成与共享 prompt builder

**Files:**
- Create: `backend/app/tasks/ai/prompt_builders.py`
- Create: `backend/app/tasks/ai/regen_character_assets_batch.py`
- Create: `backend/app/tasks/ai/regen_scene_assets_batch.py`
- Modify: `backend/app/api/prompt_profiles.py`
- Modify: `backend/app/tasks/ai/gen_character_asset.py`
- Modify: `backend/app/tasks/ai/gen_scene_asset.py`
- Test: `backend/tests/unit/test_prompt_builders.py`
- Test: `backend/tests/integration/test_prompt_profile_api.py`

- [ ] **Step 1: 先写 prompt builder 的 failing 单测**

在 `backend/tests/unit/test_prompt_builders.py` 创建：

```python
def test_build_character_asset_prompt_appends_applied_project_profile():
    project = SimpleNamespace(character_prompt_profile_applied={"prompt": "统一冷雨宫廷", "source": "ai"})
    character = SimpleNamespace(name="萧临渊", summary="summary", description="description")

    prompt = build_character_asset_prompt(project, character)

    assert "角色名称：萧临渊" in prompt
    assert "项目级统一背景提示词" in prompt
    assert "统一冷雨宫廷" in prompt


def test_build_scene_asset_prompt_without_profile_keeps_baseline():
    project = SimpleNamespace(scene_prompt_profile_applied=None)
    scene = SimpleNamespace(name="朱雀门", theme="palace", summary="summary", description="description")

    prompt = build_scene_asset_prompt(project, scene)

    assert "场景名称：朱雀门" in prompt
    assert "项目级统一背景提示词" not in prompt
```

- [ ] **Step 2: 运行测试确认 builder 尚不存在**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_prompt_builders.py -v
```

Expected: FAIL with module not found。

- [ ] **Step 3: 创建共享 prompt builder 并替换现有任务内联字符串**

创建 `backend/app/tasks/ai/prompt_builders.py`：

```python
def build_character_asset_prompt(project: Project, char: Character) -> str:
    base = (
        f"角色名称：{char.name}\n"
        f"角色简介：{char.summary}\n"
        f"角色详述：{char.description}\n"
    )
    profile = (project.character_prompt_profile_applied or {}).get("prompt")
    if profile:
        base += f"\n项目级统一背景提示词：\n{profile}\n"
    return base + "\n请生成该角色的写实人像，背景简洁。"


def build_scene_asset_prompt(project: Project, scene: Scene) -> str:
    base = (
        f"场景名称：{scene.name}\n"
        f"场景主题：{scene.theme}\n"
        f"场景简介：{scene.summary}\n"
        f"场景详述：{scene.description}\n"
    )
    profile = (project.scene_prompt_profile_applied or {}).get("prompt")
    if profile:
        base += f"\n项目级统一背景提示词：\n{profile}\n"
    return base + "\n请生成该场景的写实环境图。"
```

在 `gen_character_asset.py` / `gen_scene_asset.py` 改为：

```python
project = await session.get(Project, char.project_id)
prompt = build_character_asset_prompt(project, char)
```

和：

```python
project = await session.get(Project, scene.project_id)
prompt = build_scene_asset_prompt(project, scene)
```

- [ ] **Step 4: 先写 confirm endpoint 的 failing 测试**

在 `backend/tests/integration/test_prompt_profile_api.py` 追加：

```python
@pytest.mark.asyncio
async def test_confirm_character_prompt_profile_applies_draft_and_starts_batch_regen(client, db_session, monkeypatch):
    project = await seed_project(
        db_session,
        stage="storyboard_ready",
        character_prompt_profile_draft={"prompt": "统一冷雨宫廷", "source": "manual"},
    )
    await seed_character(db_session, project_id=project.id, name="A", locked=False)

    dispatched: dict[str, str] = {}

    def fake_delay(project_id: str, job_id: str) -> None:
        dispatched["project_id"] = project_id
        dispatched["job_id"] = job_id

    monkeypatch.setattr("app.api.prompt_profiles.regen_character_assets_batch.delay", fake_delay)

    resp = await client.post(f"/api/v1/projects/{project.id}/prompt-profiles/character/confirm")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["job_id"] == dispatched["job_id"]

    await db_session.refresh(project)
    assert project.character_prompt_profile_applied["prompt"] == "统一冷雨宫廷"
```

- [ ] **Step 5: 实现 confirm 与批量重生成 job**

在 `backend/app/api/prompt_profiles.py` 增加：

```python
@router.post("/{kind}/confirm", response_model=Envelope[GenerateJobAck])
async def confirm_prompt_profile(...):
    ...
    draft = project.character_prompt_profile_draft if kind == "character" else project.scene_prompt_profile_draft
    if not draft or not draft.get("prompt"):
        raise ApiError(40001, "请先生成或填写草稿", http_status=422)

    if kind == "character":
        project.character_prompt_profile_applied = draft
        has_assets = bool((await db.execute(select(func.count(Character.id)).where(Character.project_id == project_id))).scalar())
        job = Job(project_id=project_id, kind="regen_character_assets_batch" if has_assets else "extract_characters", status="queued", progress=0, done=0, total=None)
        db.add(job)
        await db.commit()
        if has_assets:
            regen_character_assets_batch.delay(project_id, job.id)
        else:
            extract_characters.delay(project_id, job.id)
    ...
```

创建批量重生成任务：

```python
async def _run(project_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await update_job_progress(session, job_id, status="running", progress=10)
        chars = (
            await session.execute(
                select(Character).where(Character.project_id == project_id, Character.locked.is_(False))
            )
        ).scalars().all()
        await update_job_progress(session, job_id, total=len(chars), done=0, progress=20)
        for char in chars:
            child = Job(project_id=project_id, parent_id=job_id, kind="gen_character_asset_single", status="queued", target_type="character", target_id=char.id)
            session.add(child)
            await session.flush()
            gen_character_asset.delay(char.id, child.id)
        await session.commit()
```

场景版本同理，筛 `Scene.locked.is_(False)`，子任务是 `gen_scene_asset_single`。

- [ ] **Step 6: 运行测试确认 prompt builder 与 confirm 流程通过**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_prompt_builders.py tests/integration/test_prompt_profile_api.py -k "confirm_character_prompt_profile or prompt_builders" -v
```

Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/app/tasks/ai/prompt_builders.py \
  backend/app/tasks/ai/regen_character_assets_batch.py \
  backend/app/tasks/ai/regen_scene_assets_batch.py \
  backend/app/api/prompt_profiles.py \
  backend/app/tasks/ai/gen_character_asset.py \
  backend/app/tasks/ai/gen_scene_asset.py \
  backend/tests/unit/test_prompt_builders.py \
  backend/tests/integration/test_prompt_profile_api.py
git commit -m "feat(backend): confirm prompt profiles and batch regenerate assets"
```

## Task 5: 前端类型、API 与 workbench store

**Files:**
- Create: `frontend/src/api/promptProfiles.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/store/workbench.ts`
- Test: `frontend/tests/unit/prompt-profiles.api.spec.ts`
- Test: `frontend/tests/unit/workbench.prompt-profiles.spec.ts`

- [ ] **Step 1: 先写 API client 的 failing 测试**

创建 `frontend/tests/unit/prompt-profiles.api.spec.ts`：

```ts
import { describe, expect, it, vi } from "vitest";
import { client } from "@/api/client";
import { promptProfilesApi } from "@/api/promptProfiles";

vi.mock("@/api/client", () => ({
  client: { post: vi.fn(), patch: vi.fn(), delete: vi.fn() }
}));

it("confirmCharacter posts to the confirm endpoint", async () => {
  vi.mocked(client.post).mockResolvedValue({ data: { job_id: "job1", sub_job_ids: [] } });
  await promptProfilesApi.confirm("p1", "character");
  expect(client.post).toHaveBeenCalledWith("/projects/p1/prompt-profiles/character/confirm");
});
```

- [ ] **Step 2: 运行测试确认 API 文件尚不存在**

Run:

```bash
cd frontend
npm run test -- prompt-profiles.api.spec.ts
```

Expected: FAIL with module not found。

- [ ] **Step 3: 在类型系统中加入 prompt profile contract**

在 `frontend/src/types/api.ts` 追加：

```ts
export type PromptProfileKind = "character" | "scene";
export type PromptProfileStatus = "empty" | "draft_only" | "applied" | "dirty";

export interface PromptProfilePayload {
  prompt: string;
  source: "ai" | "manual";
}

export interface PromptProfileState {
  draft: PromptProfilePayload | null;
  applied: PromptProfilePayload | null;
  status: PromptProfileStatus;
}
```

在 `frontend/src/types/index.ts` 的 `ProjectData` 增加：

```ts
  characterPromptProfile: PromptProfileState;
  scenePromptProfile: PromptProfileState;
```

- [ ] **Step 4: 新建 API client**

创建 `frontend/src/api/promptProfiles.ts`：

```ts
import { client } from "./client";
import type { GenerateJobAck, PromptProfileKind, PromptProfileState } from "@/types/api";

export const promptProfilesApi = {
  generate(projectId: string, kind: PromptProfileKind): Promise<GenerateJobAck> {
    return client.post(`/projects/${projectId}/prompt-profiles/${kind}/generate`).then((r) => r.data as GenerateJobAck);
  },
  update(projectId: string, kind: PromptProfileKind, prompt: string): Promise<PromptProfileState> {
    return client.patch(`/projects/${projectId}/prompt-profiles/${kind}`, { prompt }).then((r) => r.data as PromptProfileState);
  },
  clearDraft(projectId: string, kind: PromptProfileKind): Promise<PromptProfileState> {
    return client.delete(`/projects/${projectId}/prompt-profiles/${kind}/draft`).then((r) => r.data as PromptProfileState);
  },
  confirm(projectId: string, kind: PromptProfileKind): Promise<GenerateJobAck> {
    return client.post(`/projects/${projectId}/prompt-profiles/${kind}/confirm`).then((r) => r.data as GenerateJobAck);
  }
};
```

- [ ] **Step 5: 在 workbench store 中接入草稿 job 与 confirm 流程**

在 `frontend/src/store/workbench.ts` 增加状态：

```ts
const promptProfileJobs = ref<Record<PromptProfileKind, { projectId: string; jobId: string } | null>>({
  character: null,
  scene: null
});
```

并新增 action：

```ts
async function generatePromptProfile(kind: PromptProfileKind): Promise<string> {
  if (!current.value) throw new Error("no current project");
  const ack = await promptProfilesApi.generate(current.value.id, kind);
  promptProfileJobs.value[kind] = { projectId: current.value.id, jobId: ack.job_id };
  return ack.job_id;
}

async function savePromptProfileDraft(kind: PromptProfileKind, prompt: string) {
  if (!current.value) throw new Error("no current project");
  await promptProfilesApi.update(current.value.id, kind, prompt);
  await reload();
}

async function clearPromptProfileDraft(kind: PromptProfileKind) {
  if (!current.value) throw new Error("no current project");
  await promptProfilesApi.clearDraft(current.value.id, kind);
  await reload();
}

async function confirmPromptProfileAndGenerate(kind: PromptProfileKind): Promise<string> {
  if (!current.value) throw new Error("no current project");
  const ack = await promptProfilesApi.confirm(current.value.id, kind);
  if (kind === "character") generateCharactersJob.value = { projectId: current.value.id, jobId: ack.job_id };
  else generateScenesJob.value = { projectId: current.value.id, jobId: ack.job_id };
  await reload();
  return ack.job_id;
}
```

- [ ] **Step 6: 运行前端 API/store 单测**

Run:

```bash
cd frontend
npm run test -- prompt-profiles.api.spec.ts workbench.prompt-profiles.spec.ts
```

Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/promptProfiles.ts \
  frontend/src/types/api.ts \
  frontend/src/types/index.ts \
  frontend/src/store/workbench.ts \
  frontend/tests/unit/prompt-profiles.api.spec.ts \
  frontend/tests/unit/workbench.prompt-profiles.spec.ts
git commit -m "feat(frontend): add prompt profile API and store support"
```

## Task 6: PromptProfileCard 与角色/场景面板接入

**Files:**
- Create: `frontend/src/components/common/PromptProfileCard.vue`
- Modify: `frontend/src/components/character/CharacterAssetsPanel.vue`
- Modify: `frontend/src/components/scene/SceneAssetsPanel.vue`
- Test: `frontend/tests/unit/prompt-profile-card.spec.ts`
- Test: `frontend/tests/unit/scene.assets.panel.spec.ts`
- Test: `frontend/tests/unit/characters.api.spec.ts`

- [ ] **Step 1: 先写卡片状态渲染的 failing 测试**

创建 `frontend/tests/unit/prompt-profile-card.spec.ts`：

```ts
import { mount } from "@vue/test-utils";
import PromptProfileCard from "@/components/common/PromptProfileCard.vue";

it("shows dirty hint when draft differs from applied", () => {
  const wrapper = mount(PromptProfileCard, {
    props: {
      kind: "character",
      profile: {
        draft: { prompt: "新稿", source: "manual" },
        applied: { prompt: "旧稿", source: "ai" },
        status: "dirty"
      },
      busy: false,
      locked: false
    }
  });

  expect(wrapper.text()).toContain("当前生成仍使用上次确认版本");
  expect(wrapper.text()).toContain("确认并生成角色资产");
});
```

- [ ] **Step 2: 运行测试确认组件尚不存在**

Run:

```bash
cd frontend
npm run test -- prompt-profile-card.spec.ts
```

Expected: FAIL with module not found。

- [ ] **Step 3: 创建通用卡片组件**

创建 `frontend/src/components/common/PromptProfileCard.vue`，核心脚本：

```vue
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { PromptProfileKind, PromptProfileState } from "@/types/api";

const props = defineProps<{
  kind: PromptProfileKind;
  profile: PromptProfileState;
  busy: boolean;
  locked: boolean;
}>();

const emit = defineEmits<{
  generateAi: [];
  saveDraft: [prompt: string];
  clearDraft: [];
  confirmAndGenerate: [];
  skipGenerate: [];
}>();

const draftText = ref("");

watch(
  () => props.profile.draft?.prompt,
  (value) => {
    draftText.value = value ?? "";
  },
  { immediate: true }
);

const title = computed(() => props.kind === "character" ? "统一背景提示词" : "统一背景提示词");
const confirmLabel = computed(() => props.kind === "character" ? "确认并生成角色资产" : "确认并生成场景资产");
</script>
```

模板至少包含:

- 状态 pill
- 多行 textarea
- dirty 提示
- `AI 生成建议`
- `保存草稿`
- `清空草稿`
- `确认并生成角色资产/场景资产`
- `跳过并直接生成角色资产/场景资产`

- [ ] **Step 4: 在角色/场景面板顶部接入卡片**

在 `CharacterAssetsPanel.vue` 顶部 `actions` 之前插入：

```vue
<PromptProfileCard
  :kind="'character'"
  :profile="current.characterPromptProfile"
  :busy="busy || !!activeGenerateCharactersJobId"
  :locked="!flags.canEditCharacters"
  @generate-ai="store.generatePromptProfile('character')"
  @save-draft="(prompt) => store.savePromptProfileDraft('character', prompt)"
  @clear-draft="store.clearPromptProfileDraft('character')"
  @confirm-and-generate="store.confirmPromptProfileAndGenerate('character')"
  @skip-generate="handleGenerate"
/>
```

在 `SceneAssetsPanel.vue` 同样接 `scene` 版本，并将 `@skip-generate` 接到 `handleGenerate`。

- [ ] **Step 5: 用现有阶段门禁包住卡片操作**

在两个 panel 内统一加保护：

```ts
function ensureProfileEditable(kind: "character" | "scene"): boolean {
  const canEdit = kind === "character" ? flags.value.canEditCharacters : flags.value.canEditScenes;
  if (!canEdit) {
    toast.warning("当前阶段已锁定,如需修改请回退阶段", {
      action: { label: "回退阶段", onClick: () => (rollbackOpen.value = true) }
    });
    return false;
  }
  return true;
}
```

卡片相关事件先过这层，再调 store。

- [ ] **Step 6: 运行组件测试**

Run:

```bash
cd frontend
npm run test -- prompt-profile-card.spec.ts scene.assets.panel.spec.ts characters.api.spec.ts
```

Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/common/PromptProfileCard.vue \
  frontend/src/components/character/CharacterAssetsPanel.vue \
  frontend/src/components/scene/SceneAssetsPanel.vue \
  frontend/tests/unit/prompt-profile-card.spec.ts \
  frontend/tests/unit/scene.assets.panel.spec.ts \
  frontend/tests/unit/characters.api.spec.ts
git commit -m "feat(frontend): add prompt profile panels"
```

## Task 7: 文档、回归测试与 smoke

**Files:**
- Modify: `backend/README.md`
- Modify: `frontend/README.md`
- Modify: `frontend/src/utils/error.ts`
- Test: `backend/tests/integration/test_prompt_profile_api.py`
- Test: `backend/tests/unit/test_prompt_builders.py`
- Test: `frontend/tests/unit/workbench.prompt-profiles.spec.ts`

- [ ] **Step 1: 补错误文案与 README 说明**

在 `frontend/src/utils/error.ts` 增加：

```ts
case ERROR_CODE.CONFLICT:
  return message || "已有同类生成任务进行中";
```

在 `backend/README.md` 与 `frontend/README.md` 增加一段：

```md
### Project prompt profiles

- 角色与场景统一背景提示词均为项目级可选配置
- `draft` 只用于编辑，`applied` 才会参与具体资产生成
- “跳过并直接生成”继续走原有 `/characters/generate` 与 `/scenes/generate`
```

- [ ] **Step 2: 运行后端测试集合**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_prompt_builders.py tests/integration/test_prompt_profile_api.py -v
```

Expected: PASS。

- [ ] **Step 3: 运行前端测试集合**

Run:

```bash
cd frontend
npm run test -- prompt-profiles.api.spec.ts prompt-profile-card.spec.ts workbench.prompt-profiles.spec.ts
```

Expected: PASS。

- [ ] **Step 4: 手工 smoke 核对**

Run:

```bash
cd backend
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

另开终端：

```bash
cd frontend
npm run dev
```

手工验证：

- 新建项目并完成解析到角色阶段
- 在角色面板 AI 生成统一背景提示词草稿
- 手工修改后点击“确认并生成角色资产”
- 确认项目详情刷新后 `characterPromptProfile.status === "applied"`
- 在场景阶段重复同样流程
- 删除草稿后已应用版本仍保留

- [ ] **Step 5: Commit**

```bash
git add backend/README.md frontend/README.md frontend/src/utils/error.ts
git commit -m "docs: document project prompt profile workflow"
```

## Self-Review

- Spec coverage:
  - 项目级两套配置: Task 1, Task 2
  - `draft/applied` 双版本: Task 1, Task 2, Task 5, Task 6
  - AI 草稿生成: Task 3
  - confirm 后触发首次生成或批量重生成: Task 4
  - 无配置时 skip 复用现有流程: Task 6, Task 7
  - 不改 `render_shot`: 计划未触碰渲染链路文件，符合 spec
- Placeholder scan:
  - 所有新增端点、任务、类型、测试文件均给出确切路径与示例代码，无 `TODO/TBD`
- Type consistency:
  - 后端统一使用 `PromptProfilePayload` / `PromptProfileState`
  - 前端统一使用 `PromptProfileKind` / `PromptProfileState`
  - `status` 固定为 `empty | draft_only | applied | dirty`

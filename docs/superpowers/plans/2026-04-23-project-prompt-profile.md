# Project Prompt Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为项目新增角色/场景两套可选的统一视觉设定配置，将其作为项目级视觉圣经，支持“先生成/编辑草稿，再确认并触发具体资产生成”，并让分镜工作台的 `render-draft` 继承同一套视觉规则；无配置时保持现有角色图/场景图/镜头草稿行为不变。

**Architecture:** 后端以 `Project` 上的 `draft/applied` 双版本 JSON 字段承载 prompt profile，通过独立的 `prompt_profiles` router 暴露 `generate / patch / clear / confirm` 动作；具体角色图、场景图和镜头 `render-draft` 改为调用共享 prompt builder，只读取 `applied`。前端在角色/场景面板顶部新增统一视觉设定卡片，状态以 `GET /projects/{id}` 聚合快照为准；分镜工作台不新增第三套 profile 资源，而是在 `GenerationPanel` 中消费同一套项目视觉规则。

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
- `render-draft` builder 继承项目级视觉设定与已确认资产锚点
- 前端 PromptProfileCard、API、store、面板接入与单测

**Excludes:**

- `render_shot` provider 执行协议改造
- 新增 `project.stage`
- 独立的 `storyboard prompt profile` 资源
- 复杂 prompt 结构编辑器（负向提示词、标签权重等）
- 自动重生成已锁定角色/场景

## Current Baseline Notes

- 角色图和场景图 prompt 仍写死在 `gen_character_asset.py` / `gen_scene_asset.py` 内，且没有项目级上下文注入点。
- `ProjectDetail` 聚合目前没有任何项目级 prompt profile 字段，前端刷新后无法恢复草稿/生效版本状态。
- 角色与场景生成都已经是异步 job；新增配置草稿生成必须延续这一模式，不能在 HTTP 线程里直接调远程 AI。
- `CharacterAssetsPanel.vue` 与 `SceneAssetsPanel.vue` 顶部已有可用视觉留白，适合作为统一视觉设定配置区，不需要引入新页面或新 stage。
- `ShotRenderService.build_render_draft()` 当前只把 shot 文案和候选 references 拼成一句摘要式 prompt，还没有继承项目级视觉规则，也没有显式表达站位/镜头目标/单主运镜约束。
- `update_job_progress()` 当前只允许写 `jobs.status/progress/done/total/error_msg`；本计划必须保持这条不变量，`job.result` 需要由 service/task 显式赋值后再 `commit()`，不能往 `update_job_progress()` 里偷加 `result=` 参数。

## File Structure

**Create:**

```text
backend/alembic/versions/6f9f0c2d0d6b_add_project_prompt_profiles.py
backend/app/api/prompt_profiles.py
backend/app/domain/schemas/prompt_profile.py
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
backend/app/domain/services/shot_render_service.py
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
- Create: `backend/app/domain/schemas/prompt_profile.py`
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

迁移头信息显式写为：

```python
revision: str = "6f9f0c2d0d6b"
down_revision: Union[str, None] = "f8c1f7b6d3aa"
```

- [ ] **Step 4: 增加 prompt profile schema 与聚合输出**

在 `backend/app/domain/schemas/prompt_profile.py` 创建：

```python
class PromptProfilePayload(BaseModel):
    prompt: str = Field(min_length=1)
    source: Literal["ai", "manual"]

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt 不能为空")
        return value


class PromptProfileState(BaseModel):
    draft: PromptProfilePayload | None = None
    applied: PromptProfilePayload | None = None
    status: Literal["empty", "draft_only", "applied", "dirty"] = "empty"
```

在同文件追加纯函数，供 aggregate/service/API 共用：

```python
def derive_prompt_profile_state(
    draft: dict | None,
    applied: dict | None,
) -> PromptProfileState:
    if not draft and not applied:
        return PromptProfileState(draft=None, applied=None, status="empty")
    if draft and not applied:
        return PromptProfileState(draft=draft, applied=None, status="draft_only")
    if not draft and applied:
        return PromptProfileState(draft=None, applied=applied, status="applied")
    if draft == applied:
        return PromptProfileState(draft=draft, applied=applied, status="applied")
    return PromptProfileState(draft=draft, applied=applied, status="dirty")
```

补一条实现约束说明:

- 首版保留 `draft == applied` 时两者都可返回,前端必须严格按 `status` 渲染按钮矩阵
- 不要在聚合层把 `draft != null` 直接解释成“仍有未应用草稿”

并把 `ProjectDetail` 扩展为：

```python
    characterPromptProfile: PromptProfileState = PromptProfileState()
    scenePromptProfile: PromptProfileState = PromptProfileState()
```

在 `backend/app/domain/services/aggregate_service.py` 改为导入该 helper：

```python
from app.domain.schemas.prompt_profile import derive_prompt_profile_state
```

并在 `ProjectDetail(...)` 中填充：

```python
            characterPromptProfile=derive_prompt_profile_state(
                project.character_prompt_profile_draft,
                project.character_prompt_profile_applied,
            ),
            scenePromptProfile=derive_prompt_profile_state(
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
  backend/app/domain/schemas/prompt_profile.py \
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

在 `backend/app/domain/schemas/prompt_profile.py` 追加：

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

在 `backend/app/domain/services/prompt_profile_service.py` 追加：

```python
class PromptProfileService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def update_draft(self, project: Project, kind: Literal["character", "scene"], prompt: str) -> PromptProfileState:
        payload = {"prompt": prompt.strip(), "source": "manual"}
        if kind == "character":
            project.character_prompt_profile_draft = payload
            return derive_prompt_profile_state(project.character_prompt_profile_draft, project.character_prompt_profile_applied)
        project.scene_prompt_profile_draft = payload
        return derive_prompt_profile_state(project.scene_prompt_profile_draft, project.scene_prompt_profile_applied)

    def clear_draft(self, project: Project, kind: Literal["character", "scene"]) -> PromptProfileState:
        if kind == "character":
            project.character_prompt_profile_draft = None
            return derive_prompt_profile_state(project.character_prompt_profile_draft, project.character_prompt_profile_applied)
        project.scene_prompt_profile_draft = None
        return derive_prompt_profile_state(project.scene_prompt_profile_draft, project.scene_prompt_profile_applied)
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
    if kind not in ("character", "scene"):
        raise ApiError(40001, f"非法 kind: {kind}", http_status=422)
    _assert_profile_editable(project, kind)
    state = svc.update_draft(project, kind, payload.prompt)
    await db.commit()
    return ok(state)


@router.delete("/{kind}/draft")
async def clear_prompt_profile_draft(...):
    ...
    if kind not in ("character", "scene"):
        raise ApiError(40001, f"非法 kind: {kind}", http_status=422)
    _assert_profile_editable(project, kind)
    state = svc.clear_draft(project, kind)
    await db.commit()
    return ok(state)
```

并在 `backend/app/main.py` 注册：

```python
from app.api import ..., prompt_profiles
...
app.include_router(prompt_profiles.router, prefix="/api/v1")
```

- [ ] **Step 5: 运行测试确认 PATCH / DELETE 与 403 门禁通过**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_prompt_profile_api.py -k "patch_character_prompt_profile or delete_scene_prompt_profile" -v
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/prompt_profiles.py \
  backend/app/domain/services/prompt_profile_service.py \
  backend/app/main.py \
  backend/app/domain/schemas/prompt_profile.py \
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


@pytest.mark.asyncio
async def test_generate_character_prompt_profile_returns_409_when_same_lane_job_running(client, db_session):
    project = await seed_project(db_session, stage="storyboard_ready")
    db_session.add(
        Job(
            project_id=project.id,
            kind="gen_character_prompt_profile",
            status="running",
            progress=20,
        )
    )
    await db_session.commit()

    resp = await client.post(f"/api/v1/projects/{project.id}/prompt-profiles/character/generate")
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == 40901
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
    settings = get_settings()
    async with session_factory() as session:
        await update_job_progress(session, job_id, status="running", progress=10)
        project = await session.get(Project, project_id)
        system_prompt = (
            "你是漫剧项目的视觉设定师。"
            "请只返回 JSON 对象，字段固定为 prompt。"
            "prompt 必须是一段中文自然语言，显式覆盖以下 7 个维度："
            "world_era、visual_style、palette_lighting、lens_language、"
            "character_rules、scene_rules、negative_rules。"
            "不要返回 markdown，不要返回解释，不要省略字段语义。"
        )
        user_prompt = (
            "请基于项目故事概述、setup_params、项目摘要、已识别角色与分镜信息，"
            "生成一段适合所有角色参考图复用的统一视觉设定。"
        )
        response = await get_volcano_client().chat_completions(
            model=settings.ark_chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        payload = {"prompt": extract_json(content)["prompt"].strip(), "source": "ai"}
        project.character_prompt_profile_draft = payload
        job = await session.get(Job, job_id)
        job.result = {"profile_kind": "character"}
        await update_job_progress(session, job_id, status="succeeded", progress=100)
        await session.commit()
```

场景任务同理，只改写 `scene_prompt_profile_draft`，system prompt 保持同一骨架，user prompt 改成强调“适合所有场景母版图复用”。

实现时统一沿用 `parse_novel.py` / `extract_characters.py` 的读取方式: 先取 `response.choices[0].message.content` 字符串，再 `extract_json(content)`，不要假设 `chat_completions()` 已直接返回 dict。

- [ ] **Step 4: 暴露 generate 端点**

在 `backend/app/api/prompt_profiles.py` 增加：

```python
async def _assert_profile_editable_and_not_running(
    db: AsyncSession,
    project: Project,
    kind: Literal["character", "scene"],
    *,
    check_profile_job: bool,
    check_asset_job: bool,
) -> None:
    ...


@router.post("/{kind}/generate", response_model=Envelope[GenerateJobAck])
async def generate_prompt_profile(...):
    ...
    if kind not in ("character", "scene"):
        raise ApiError(40001, f"非法 kind: {kind}", http_status=422)
    stmt = select(Project).where(Project.id == project_id).with_for_update()
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise ApiError(40401, "项目不存在", http_status=404)
    await _assert_profile_editable_and_not_running(
        db,
        project,
        kind,
        check_profile_job=True,
        check_asset_job=True,
    )
    job = Job(project_id=project_id, kind=f"gen_{kind}_prompt_profile", status="queued", progress=0, done=0, total=None)
    db.add(job)
    await db.commit()
    try:
        if kind == "character":
            gen_character_prompt_profile.delay(project_id, job.id)
        else:
            gen_scene_prompt_profile.delay(project_id, job.id)
    except Exception as exc:
        await update_job_progress(db, job.id, status="failed", error_msg=f"dispatch failed: {exc}")
        await db.commit()
        raise
    return Envelope.success(GenerateJobAck(job_id=job.id, sub_job_ids=[]))
```

要求 `_assert_profile_editable_and_not_running(...)` 在 service/router 层显式查询同项目 `queued/running` 的 in-flight job:

- `check_profile_job=True` 时拦截 `gen_{kind}_prompt_profile`
- `check_asset_job=True` 时拦截角色侧 `extract_characters` / `gen_character_asset` / `regen_character_assets_batch`，以及场景侧 `gen_scene_asset` / `regen_scene_assets_batch`
- 命中时统一抛 `ApiError(40901, "已有同类生成任务进行中", http_status=409)`

- [ ] **Step 5: 运行测试确认生成 job ack 正常**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_prompt_profile_api.py -k "generate_character_prompt_profile_returns_job_ack or generate_character_prompt_profile_returns_409" -v
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

## Task 4a: confirm、批量重生成与共享 asset prompt builder

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
def test_build_character_asset_prompt_places_project_visual_profile_before_character_details():
    project = SimpleNamespace(character_prompt_profile_applied={"prompt": "中国现代雨夜都市，冷青灰色板，克制侧逆光，禁止风格漂移", "source": "ai"})
    character = SimpleNamespace(name="萧临渊", summary="summary", description="description")

    prompt = build_character_asset_prompt(project, character)

    assert "项目级统一视觉设定" in prompt
    assert prompt.index("项目级统一视觉设定") < prompt.index("角色名称：萧临渊")
    assert "角色设定参考图" in prompt
    assert "禁止风格漂移" in prompt
    assert "角色名称：萧临渊" in prompt


def test_build_scene_asset_prompt_without_profile_keeps_baseline_scene_master_intent():
    project = SimpleNamespace(scene_prompt_profile_applied=None)
    scene = SimpleNamespace(name="朱雀门", theme="palace", summary="summary", description="description")

    prompt = build_scene_asset_prompt(project, scene)

    assert "场景名称：朱雀门" in prompt
    assert "项目级统一视觉设定" not in prompt
    assert "场景设定参考图" in prompt
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
    profile = (project.character_prompt_profile_applied or {}).get("prompt")
    sections = []
    if profile:
        sections.append(f"项目级统一视觉设定：\n{profile}")
    sections.append(
        f"用途：生成角色设定参考图，用于后续分镜与视频生成的一致性锁定。\n"
        f"角色名称：{char.name}\n"
        f"角色简介：{char.summary}\n"
        f"角色详述：{char.description}\n"
        "画面要求：单人，全身或七分身，主体明确，背景简洁，便于复用。\n"
        "禁止项：禁止多人，禁止复杂背景，禁止额外道具，禁止风格漂移，禁止文字水印。"
    )
    return "\n\n".join(sections)


def build_scene_asset_prompt(project: Project, scene: Scene) -> str:
    profile = (project.scene_prompt_profile_applied or {}).get("prompt")
    sections = []
    if profile:
        sections.append(f"项目级统一视觉设定：\n{profile}")
    sections.append(
        f"用途：生成场景设定参考图，用于后续分镜静帧与视频镜头的场景一致性锁定。\n"
        f"场景名称：{scene.name}\n"
        f"场景主题：{scene.theme}\n"
        f"场景简介：{scene.summary}\n"
        f"场景详述：{scene.description}\n"
        "画面要求：突出关键结构与空间层次，可弱化人物或不出现人物，便于复用。\n"
        "禁止项：禁止结构混乱，禁止无关人物抢画面，禁止时代错置，禁止风格漂移，禁止文字水印。"
    )
    return "\n\n".join(sections)
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


@pytest.mark.asyncio
async def test_confirm_character_prompt_profile_returns_409_when_asset_lane_running(client, db_session):
    project = await seed_project(
        db_session,
        stage="storyboard_ready",
        character_prompt_profile_draft={"prompt": "统一冷雨宫廷", "source": "manual"},
    )
    db_session.add(
        Job(
            project_id=project.id,
            kind="regen_character_assets_batch",
            status="queued",
            progress=0,
        )
    )
    await db_session.commit()

    resp = await client.post(f"/api/v1/projects/{project.id}/prompt-profiles/character/confirm")
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == 40901


@pytest.mark.asyncio
async def test_confirm_scene_prompt_profile_with_all_locked_targets_finishes_as_noop(client, db_session, monkeypatch):
    project = await seed_project(
        db_session,
        stage="characters_locked",
        scene_prompt_profile_draft={"prompt": "冷青皇城", "source": "manual"},
    )
    await seed_scene(db_session, project_id=project.id, name="S1", locked=True)

    def fail_delay(*args, **kwargs):
        raise AssertionError("should not dispatch child jobs when all scenes are locked")

    monkeypatch.setattr("app.api.prompt_profiles.regen_scene_assets_batch.delay", fail_delay)

    resp = await client.post(f"/api/v1/projects/{project.id}/prompt-profiles/scene/confirm")
    assert resp.status_code == 200
    ack = resp.json()["data"]
    assert ack["job_id"]

    batch_job = await db_session.get(Job, ack["job_id"])
    assert batch_job.status == "succeeded"
    assert batch_job.total == 0
    assert batch_job.done == 0
    assert batch_job.result["skipped_locked_count"] == 1
```

- [ ] **Step 5: 实现 confirm 与批量重生成 job**

在 `backend/app/api/prompt_profiles.py` 增加：

```python
async def _assert_profile_editable_and_not_running(
    db: AsyncSession,
    project: Project,
    kind: Literal["character", "scene"],
    *,
    check_profile_job: bool,
    check_asset_job: bool,
) -> None:
    ...


@router.post("/{kind}/confirm", response_model=Envelope[GenerateJobAck])
async def confirm_prompt_profile(...):
    ...
    if kind not in ("character", "scene"):
        raise ApiError(40001, f"非法 kind: {kind}", http_status=422)
    stmt = select(Project).where(Project.id == project_id).with_for_update()
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise ApiError(40401, "项目不存在", http_status=404)
    await _assert_profile_editable_and_not_running(
        db,
        project,
        kind,
        check_profile_job=False,
        check_asset_job=True,
    )
    draft = project.character_prompt_profile_draft if kind == "character" else project.scene_prompt_profile_draft
    if not draft or not draft.get("prompt"):
        raise ApiError(40001, "请先生成或填写草稿", http_status=422)

    if kind == "character":
        current_rows = (await db.execute(select(func.count(Character.id)).where(Character.project_id == project_id))).scalar() or 0
        next_kind = "regen_character_assets_batch" if current_rows > 0 else "extract_characters"
        previous_applied = project.character_prompt_profile_applied
        project.character_prompt_profile_applied = draft
        job = Job(project_id=project_id, kind=next_kind, status="queued", progress=0, done=0, total=None)
        db.add(job)
        await db.commit()
        try:
            if next_kind == "regen_character_assets_batch":
                regen_character_assets_batch.delay(project_id, job.id)
            else:
                extract_characters.delay(project_id, job.id)
        except Exception as exc:
            stmt = select(Project).where(Project.id == project_id).with_for_update()
            locked_project = (await db.execute(stmt)).scalar_one()
            locked_project.character_prompt_profile_applied = previous_applied
            await update_job_progress(db, job.id, status="failed", error_msg=f"dispatch failed: {exc}")
            await db.commit()
            raise
    ...
```

说明:

- `confirm` 必须在 `with_for_update()` 锁住项目后执行，避免同项目并发 confirm/生成交叉覆盖
- `applied = draft` 与主 job 创建在同一事务里提交
- 若 `delay()` 失败，立即在补偿事务里把 `applied` 恢复为 confirm 前快照，并把主 job 标记为 `failed`；不要留下“配置已生效但生成根本没发出去”的半成功状态
- `current_rows == 0` 视为“当前项目没有可复用的角色/场景记录”，即使项目曾经进入过后续 stage，也按首次生成路径重新走 `extract_characters` / `generate scenes`

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
        locked_count = (
            await session.execute(
                select(func.count(Character.id)).where(Character.project_id == project_id, Character.locked.is_(True))
            )
        ).scalar() or 0
        if not chars:
            job = await session.get(Job, job_id)
            job.result = {"skipped_locked_count": int(locked_count)}
            await update_job_progress(session, job_id, status="succeeded", total=0, done=0, progress=100)
            await session.commit()
            return
        await update_job_progress(session, job_id, total=len(chars), done=0, progress=20)
        for char in chars:
            child = Job(project_id=project_id, parent_id=job_id, kind="gen_character_asset_single", status="queued", target_type="character", target_id=char.id)
            session.add(child)
            await session.flush()
            gen_character_asset.delay(char.id, child.id)
        await session.commit()
```

场景版本同理，筛 `Scene.locked.is_(False)`，子任务是 `gen_scene_asset_single`；若结果集为空，同样先赋值 `job.result = {"skipped_locked_count": <count>}`，再调用 `update_job_progress(...)` 标记父 job 成功。

- [ ] **Step 6: 运行测试确认 prompt builder 与 confirm 流程通过**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_prompt_builders.py tests/integration/test_prompt_profile_api.py -k "confirm_character_prompt_profile or confirm_scene_prompt_profile_with_all_locked_targets or prompt_builders" -v
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
git commit -m "feat(backend): align prompt profiles with asset builders"
```

## Task 4b: render-draft 继承项目级视觉设定

**Files:**
- Modify: `backend/app/domain/services/shot_render_service.py`
- Modify: `backend/app/tasks/ai/prompt_builders.py`
- Test: `backend/tests/integration/test_shot_render_api.py`

- [ ] **Step 1: 先写 render-draft 继承项目视觉设定的 failing 测试**

在 `backend/tests/integration/test_shot_render_api.py` 追加：

```python
@pytest.mark.asyncio
async def test_build_render_draft_includes_applied_project_visual_profiles(db_session):
    project = await seed_project(
        db_session,
        stage="scenes_locked",
        character_prompt_profile_applied={"prompt": "东方面孔，冷青灰色板，角色五官稳定", "source": "ai"},
        scene_prompt_profile_applied={"prompt": "雨夜都市，克制侧逆光，空间结构稳定", "source": "ai"},
    )
    shot = await seed_shot(db_session, project_id=project.id, title="雨夜对峙", description="主角在街口回头", detail="中近景")
    ...
    draft = await ShotRenderService(db_session).build_render_draft(project.id, shot.id)
    assert "项目级统一视觉设定" in draft["prompt"]
    assert "角色五官稳定" in draft["prompt"]
    assert "空间结构稳定" in draft["prompt"]
```

在 `backend/app/tasks/ai/prompt_builders.py` 增加：

```python
def build_storyboard_render_draft_prompt(
    project: Project,
    shot: StoryboardShot,
    references: list[dict[str, Any]],
) -> str:
    ...
```

在 `backend/app/domain/services/shot_render_service.py` 中，把当前 `_build_draft_prompt()` 拆到共享 builder 或调用 `build_storyboard_render_draft_prompt()`，确保输出至少包含:

- 项目级统一视觉设定
- shot 标题/描述/detail/tags
- references 对应的角色名/场景名
- 镜头目标、站位/景别、单一主运镜、连续性/负向约束的提示语骨架

- [ ] **Step 2: 运行测试确认 render-draft 对齐通过**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_shot_render_api.py -k "build_render_draft_includes_applied_project_visual_profiles" -v
```

Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/app/tasks/ai/prompt_builders.py \
  backend/app/domain/services/shot_render_service.py \
  backend/tests/integration/test_shot_render_api.py
git commit -m "feat(backend): align render draft with project visual profiles"
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

export interface GenerateJobAck {
  job_id: string;
  sub_job_ids: string[];
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

并补 active id：

```ts
const activeCharacterPromptProfileJobId = computed(() =>
  scopedJobId(promptProfileJobs.value.character)
);
const activeScenePromptProfileJobId = computed(() =>
  scopedJobId(promptProfileJobs.value.scene)
);
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

async function restoreAppliedPromptProfileDraft(kind: PromptProfileKind) {
  if (!current.value) throw new Error("no current project");
  const profile = kind === "character" ? current.value.characterPromptProfile : current.value.scenePromptProfile;
  const applied = profile.applied?.prompt;
  if (!applied) throw new Error("no applied profile");
  await promptProfilesApi.update(current.value.id, kind, applied);
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

async function skipPromptProfileAndGenerate(kind: PromptProfileKind): Promise<string> {
  if (!current.value) throw new Error("no current project");
  const ack =
    kind === "character"
      ? await charactersApi.generate(current.value.id)
      : await scenesApi.generate(current.value.id);
  if (kind === "character") generateCharactersJob.value = { projectId: current.value.id, jobId: ack.job_id };
  else generateScenesJob.value = { projectId: current.value.id, jobId: ack.job_id };
  await reload();
  return ack.job_id;
}
```

并在同一 store 内补一组辅助方法，供组件轮询成功/失败时调用：

```ts
function markPromptProfileJobSucceeded(kind: PromptProfileKind) {
  promptProfileJobs.value[kind] = null;
}

function markPromptProfileJobFailed(kind: PromptProfileKind) {
  promptProfileJobs.value[kind] = null;
}
```

`load()/reload()` 后若需要断点恢复：

- profile 草稿生成 job：按 `kind === "gen_character_prompt_profile" | "gen_scene_prompt_profile"` 恢复到 `promptProfileJobs`
- 资产主生成链路 job：
  - 角色侧统一归入 `generateCharactersJob`
  - 可恢复 kind 包括 `extract_characters` / `gen_character_asset` / `regen_character_assets_batch`
  - 场景侧统一归入 `generateScenesJob`
  - 可恢复 kind 包括 `gen_scene_asset` / `regen_scene_assets_batch`

这里的 store 槽位语义不是“某一个固定 job kind”，而是“当前角色/场景资产主生成链路的顶层 job”。

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
- Test: `frontend/tests/unit/character.assets.panel.spec.ts`

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
  restoreApplied: [];
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

const title = "统一视觉设定";
const confirmLabel = computed(() => props.kind === "character" ? "确认并生成角色资产" : "确认并生成场景资产");
const regenerateLabel = computed(() => props.kind === "character" ? "按当前配置重新生成角色资产" : "按当前配置重新生成场景资产");
</script>
```

模板至少包含:

- 状态 pill
- 多行 textarea
- dirty 提示
- 按 `profile.status` 切换按钮矩阵:
  - `empty`: `AI 生成建议` + `跳过并直接生成角色资产/场景资产`
  - `draft_only`: `确认并生成角色资产/场景资产` + `重新生成建议` + `保存草稿` + `清空草稿`
  - `applied`: `按当前配置重新生成角色资产/场景资产` + `编辑草稿` + `重新生成建议`
  - `dirty`: `确认新配置并生成` + `恢复到已应用版本` + `重新生成建议` + `保存草稿`

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
  @restore-applied="store.restoreAppliedPromptProfileDraft('character')"
  @skip-generate="store.skipPromptProfileAndGenerate('character')"
/>
```

在 `SceneAssetsPanel.vue` 同样接 `scene` 版本，并将 `@restore-applied` / `@skip-generate` 接到 scene 对应 action。

- [ ] **Step 5: 为角色/场景草稿生成 job 接上 `useJobPolling`**

在 `CharacterAssetsPanel.vue` 增加：

```ts
const { job: characterPromptProfileJob } = useJobPolling(activeCharacterPromptProfileJobId, {
  onProgress: () => void 0,
  onSuccess: async () => {
    await store.reload();
    store.markPromptProfileJobSucceeded("character");
    toast.success("角色统一视觉设定草稿已生成");
  },
  onError: (j, err) => {
    store.markPromptProfileJobFailed("character");
    toast.error(j?.error_msg ?? (err instanceof ApiError ? messageFor(err.code, err.message) : "草稿生成失败"));
  }
});
```

在 `SceneAssetsPanel.vue` 同样增加 scene 版本，并在卡片上给出运行态提示：

```vue
:busy="busy || !!activeGenerateScenesJobId || !!activeScenePromptProfileJobId"
```

- [ ] **Step 6: 用现有阶段门禁包住卡片操作**

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

卡片相关事件先过这层，再调 store；`skip-generate` 例外，它只需要沿用现有 `handleGenerate()` 的门禁与提示。

- [ ] **Step 7: 运行组件测试**

Run:

```bash
cd frontend
npm run test -- prompt-profile-card.spec.ts scene.assets.panel.spec.ts character.assets.panel.spec.ts
```

Expected: PASS。

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/common/PromptProfileCard.vue \
  frontend/src/components/character/CharacterAssetsPanel.vue \
  frontend/src/components/scene/SceneAssetsPanel.vue \
  frontend/tests/unit/prompt-profile-card.spec.ts \
  frontend/tests/unit/scene.assets.panel.spec.ts \
  frontend/tests/unit/character.assets.panel.spec.ts
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

在 `frontend/src/utils/error.ts` 不要新增重复 `case`；该文件当前通过 `TEXT[code]` + `messageFor()` 映射错误。直接调整现有 `ERROR_CODE.CONFLICT` 对应文案，或保持映射不变并优先透传后端 message。

```ts
const TEXT: Record<number, string> = {
  ...,
  [ERROR_CODE.CONFLICT]: "已有同类生成任务进行中，请等待当前任务完成后再试"
};
```

在 `backend/README.md` 与 `frontend/README.md` 增加一段：

```md
### Project prompt profiles

- 角色与场景统一视觉设定均为项目级可选配置
- `draft` 只用于编辑，`applied` 才会参与具体资产生成
- “跳过并直接生成”继续走原有 `/characters/generate` 与 `/scenes/generate`
- 当 `status = "applied"` 且 `draft == applied` 时，前端必须以 `status` 判断按钮矩阵，不要用 `draft != null` 误判为“草稿中”
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
- 在角色面板 AI 生成统一视觉设定草稿
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
  - `generate / confirm` 的 `40901` 并发守门: Task 3, Task 4a
  - confirm 后触发首次生成或批量重生成: Task 4a
  - `render-draft` 继承项目级视觉设定: Task 4b
  - 无配置时 skip 复用现有流程: Task 6, Task 7
  - 不改 `render_shot` provider 执行协议: Task 4b 仅调整 prompt builder / `shot_render_service.py`，未改 provider 调用协议
- Placeholder scan:
  - 所有新增端点、任务、类型、测试文件均给出确切路径与示例代码，无 `TODO/TBD`
- Type consistency:
  - 后端统一使用 `PromptProfilePayload` / `PromptProfileState`
  - 前端统一使用 `PromptProfileKind` / `PromptProfileState`
  - `status` 固定为 `empty | draft_only | applied | dirty`

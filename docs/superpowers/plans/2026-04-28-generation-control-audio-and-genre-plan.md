# Generation Control, Audio, and Genre Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix generation drift by making `genre` reliable at the source, add user-facing cancellation for async generation, extend character assets with 360 turnaround and voice metadata, and enable audio for Seedance video generation.

**Architecture:** Keep all remote AI work asynchronous through the existing `Job` + Celery pattern. Do not compensate for bad project metadata by adding prompt-level negative phrases such as "禁止古风/宫廷/权谋元素"; instead, derive `genre` from the model parse result, require the correct visual profile to be applied before dependent assets are generated, and pass complete project/profile context into downstream draft generation. Cancellation is a backend job operation with provider-specific best-effort cancellation for queued video tasks, surfaced by small frontend controls on existing progress banners.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, Celery, MySQL, Volcengine Ark / Seedance 2.0 APIs, Vue 3, TypeScript, Pinia, Axios, Vitest, pytest.

---

## References

- Root instructions: `AGENTS.md`
- Backend README: `backend/README.md`
- Frontend README: `frontend/README.md`
- Existing project prompt profile plan: `docs/superpowers/plans/2026-04-23-project-prompt-profile.md`
- Existing style reference plan: `docs/superpowers/plans/2026-04-24-character-scene-style-reference-assets.md`
- Existing shot reference and progress plan: `docs/superpowers/plans/2026-04-24-shot-reference-and-adaptive-progress.md`
- Seedance API notes:
  - `docs/huoshan_api/创建视频生成任务 API.md`
  - `docs/huoshan_api/查询视频生成任务 API.md`
  - `docs/huoshan_api/取消或删除视频生成任务.md`
  - `docs/integrations/volcengine-ark-api.md`

## Problem Summary

The observed project story and AI-derived profiles are modern apocalyptic / urban suspense, but the project aggregate still returns `genre: "古风权谋"`. That value is injected into project style reference prompts and shot draft generation context. The fix must make project metadata reliable, not add prompt-level bans against the wrong genre.

Additional issues:

- Scene style reference generation can run while `scenePromptProfile` is still only a draft.
- Character project-level visual reference includes concrete face/person information, although it should only carry visual style.
- Project-level reference images are passed as strong provider references, causing generated assets to over-copy the reference.
- Running jobs have no backend cancellation API or frontend cancel button.
- Video generation hard-codes `generate_audio: False`.
- Characters lack 360 turnaround and voice metadata fields.

## Scope

Includes:

- Remove manual genre input from project creation and update surfaces.
- Store parse-derived genre on the project from the large-model novel parsing result.
- Require scene prompt profile application before scene style reference generation.
- Narrow character style reference prompts to project-level style only.
- Lower over-copy risk by reducing reference stacking and clarifying style-only usage.
- Pass applied visual profiles into shot draft generation context.
- Add a `POST /api/v1/jobs/{job_id}/cancel` endpoint and frontend cancel controls.
- Add character 360 turnaround and voice metadata fields.
- Enable video audio through request DTOs, UI controls, and Seedance payloads.

Excludes:

- Adding prompt-level negative phrases that ban ancient/court/power-struggle terms.
- Fully automatic image quality / computer-vision validation.
- TTS provider integration beyond storing and passing voice/reference-audio metadata.
- Local file upload for voice reference audio.
- Rewriting the whole generation workflow or adding new project stages.

## File Structure

Backend create:

- `backend/alembic/versions/20260428_add_character_turnaround_and_voice.py` - migration for character 360 and voice metadata fields.
- `backend/scripts/derive_project_genre.py` - one-off model-derived project genre repair script for existing bad data.
- `backend/tests/unit/test_project_genre_resolution.py` - parse/default genre behavior tests.
- `backend/tests/unit/test_generation_prompt_integrity.py` - prompt builder and shot draft context tests.
- `backend/tests/integration/test_job_cancel_api.py` - cancel endpoint tests.
- `backend/tests/integration/test_video_audio_api.py` - video audio parameter persistence tests.

Backend modify:

- `backend/scripts/smoke_m1.sh` / `backend/scripts/smoke_m2.sh` / `frontend/scripts/smoke_m3a.sh` - remove `genre` from project create payloads.
- `backend/app/domain/schemas/project.py` - remove user-writable `genre` from create/update DTOs while keeping genre in read DTOs.
- `backend/app/domain/models/project.py` - keep the existing `genre` persistence column as a system-written AI classification result.
- `backend/app/domain/models/character.py` - add `turnaround_image_url`, `is_humanoid`, `voice_profile`, `voice_reference_audio_url`, and `voice_asset_id`.
- `backend/app/domain/schemas/character.py` - expose new character fields.
- `backend/app/domain/schemas/shot_video.py` - add `generate_audio` and optional audio reference fields.
- `backend/app/api/jobs.py` - add cancel endpoint.
- `backend/app/pipeline/transitions.py` - refresh job rows before status transitions so canceled jobs are not overwritten by stale worker sessions.
- `backend/app/api/style_references.py` / `backend/app/domain/services/style_reference_service.py` - enforce scene profile application.
- `backend/app/api/shots.py` - accept video audio options.
- `backend/app/tasks/ai/parse_novel.py` - parse and persist derived genre.
- `backend/app/tasks/ai/prompt_builders.py` - style-only character reference prompt and stronger style-only reference wording.
- `backend/app/tasks/ai/gen_character_asset.py` - generate full body, headshot, turnaround, and voice metadata in order.
- `backend/app/tasks/ai/extract_characters.py` - ask the model to mark whether each character is humanoid.
- `backend/app/tasks/ai/gen_scene_asset.py` - keep scene reference as style/layout guidance, not a layout copy target.
- `backend/app/domain/services/shot_draft_service.py` - pass profiles and summary/overview into draft context.
- `backend/app/tasks/ai/gen_shot_draft.py` - include complete context in selection/prompt messages.
- `backend/app/tasks/ai/gen_storyboard.py` / `backend/app/tasks/ai/extract_characters.py` / `backend/app/tasks/ai/extract_scenes.py` / `backend/app/tasks/ai/gen_character_prompt_profile.py` / `backend/app/tasks/ai/gen_scene_prompt_profile.py` / `backend/app/tasks/ai/gen_style_reference.py` - add cooperative cancellation checkpoints or explicitly return when job status is already canceled.
- `backend/app/domain/services/shot_video_service.py` - persist `generate_audio` and audio reference params.
- `backend/app/tasks/video/render_shot_video.py` - skip canceled jobs and pass audio options to provider.
- `backend/app/infra/volcano_client.py` - add video task delete/cancel method and support `audio_url` content.
- `backend/app/domain/services/aggregate_service.py` - expose new character fields and audio-enabled video params.
- `backend/tests/integration/test_projects_api.py` / `backend/tests/integration/test_parse_flow.py` - remove `genre` from project create API payloads.

Frontend create:

- `frontend/tests/unit/job-cancel.spec.ts` - cancel API/store behavior.
- `frontend/tests/unit/video-audio-options.spec.ts` - audio toggle behavior.

Frontend modify:

- `frontend/src/views/ProjectCreateView.vue` - remove the genre select from the create form and stop sending `genre`.
- `frontend/src/types/api.ts` - add cancel response, character fields, and video audio request fields.
- `frontend/src/api/jobs.ts` - add `cancel(jobId)`.
- `frontend/src/api/shots.ts` - send video audio fields.
- `frontend/src/store/workbench.ts` - cancel actions and video audio options.
- `frontend/src/components/setup/ProjectSetupPanel.vue` - display derived genre normally.
- `frontend/src/components/character/CharacterAssetsPanel.vue` - show turnaround and voice metadata.
- `frontend/src/components/scene/SceneAssetsPanel.vue` - disable scene style reference until scene profile is applied.
- `frontend/src/components/generation/GenerationPanel.vue` - add cancel button and audio toggle.
- `frontend/tests/unit/character.generate.chain.spec.ts` / `frontend/tests/unit/workbench.m3a.store.spec.ts` - replace misleading `古风权谋` read DTO fixtures with neutral or modern derived genres.

---

## Task 1: Make Project Genre Large-Model Derived

**Files:**

- Modify: `frontend/src/views/ProjectCreateView.vue`
- Modify: `frontend/src/types/api.ts`
- Modify: `backend/app/tasks/ai/parse_novel.py`
- Modify: `backend/app/domain/schemas/project.py`
- Test: `backend/tests/unit/test_project_genre_resolution.py`
- Modify: `backend/scripts/smoke_m1.sh`
- Modify: `backend/scripts/smoke_m2.sh`
- Modify: `frontend/scripts/smoke_m3a.sh`
- Modify: `backend/tests/integration/test_projects_api.py`
- Modify: `backend/tests/integration/test_parse_flow.py`
- Modify: `frontend/tests/unit/character.generate.chain.spec.ts`
- Modify: `frontend/tests/unit/workbench.m3a.store.spec.ts`

- [ ] **Step 1: Write backend genre tests**

Create `backend/tests/unit/test_project_genre_resolution.py`:

```python
import pytest
from pydantic import ValidationError

from app.domain.schemas.project import ProjectCreate, ProjectUpdate
from app.tasks.ai.parse_novel import normalize_parsed_genre


def test_normalize_parsed_genre_keeps_short_specific_value():
    assert normalize_parsed_genre("现代末世") == "现代末世"


def test_normalize_parsed_genre_rejects_blank_value():
    assert normalize_parsed_genre("   ") is None


def test_project_create_does_not_accept_user_genre():
    with pytest.raises(ValidationError):
        ProjectCreate(name="末世小说", story="现代末世故事", genre="古风权谋")


def test_project_create_has_no_genre_attribute():
    payload = ProjectCreate(name="末世小说", story="现代末世故事")

    assert not hasattr(payload, "genre")


def test_project_update_does_not_accept_user_genre():
    fields = ProjectUpdate.model_fields

    assert "genre" not in fields
```

- [ ] **Step 2: Run the backend test and verify it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_project_genre_resolution.py -v
```

Expected: fails because `normalize_parsed_genre` does not exist and the project DTOs still expose user-writable `genre`.

- [ ] **Step 3: Implement genre helpers and full parse schema**

In `backend/app/tasks/ai/parse_novel.py`, add helper near the JSON normalization helpers:

```python
def normalize_parsed_genre(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:64]
```

Replace the hard-coded JSON schema block inside the `prompt = f"""..."""` template with the full schema including `genre`:

```python
prompt = f"""请解析以下小说内容并返回 JSON 格式的分析结果。
要求严格遵守以下 JSON 结构：
{{
  "summary": "一句话故事梗概",
  "overview": "详细的故事背景与情节概述",
  "parsed_stats": ["角色: N", "场景: M", "预计时长: Ts"],
  "suggested_shots": 12,
  "genre": "从小说正文识别出的短题材标签,例如 现代末世、都市悬疑、科幻悬疑、古风权谋"
}}

要求：
- genre 必须只依据小说正文判断,不要沿用任何已有项目字段。
- genre 使用正向题材标签,不要通过禁止词或负面约束表达。

小说内容：
{project.story}"""
```

After parsing response JSON, persist it whenever the model returns a valid value:

```python
parsed_genre = normalize_parsed_genre(data.get("genre"))
if parsed_genre:
    project.genre = parsed_genre
```

Update `MockVolcanoClient.chat_completions()` parse response so mock parse also returns a `genre`, for example:

```python
"genre": "科幻冒险",
```

- [ ] **Step 4: Remove genre from project create/update DTOs**

In `backend/app/domain/schemas/project.py`, import `ConfigDict`, remove `genre` from `ProjectCreate` and `ProjectUpdate`, and forbid extra payload fields while keeping `genre` on read DTOs:

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator
```

```python
class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=128)
    story: str = Field(..., min_length=1)
    ratio: str = Field(default="9:16", min_length=1, max_length=16)
    setup_params: list[str] | None = None
```

```python
class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    ratio: str | None = Field(default=None, min_length=1, max_length=16)
    setup_params: list[str] | None = None
```

Update `_reject_explicit_null()` so it checks only:

```python
for field in ("name", "ratio", "setup_params"):
```

- [ ] **Step 5: Stop writing user genre during create**

In `backend/app/domain/services/project_service.py`, remove `genre=payload.genre` from `Project(...)`.

- [ ] **Step 6: Remove frontend genre field**

In `frontend/src/views/ProjectCreateView.vue`, remove `genre` from form state:

```ts
const form = ref({
  name: "",
  story: "",
  ratio: "9:16"
});
```

Remove `genre` from the create payload:

```ts
const resp = await projects.createProject({
  name: form.value.name.trim(),
  story: form.value.story.trim(),
  ratio: form.value.ratio
});
```

Remove the entire topic select block from the template. The first row should contain only the ratio select:

```vue
<label>
  <span>画幅比例</span>
  <select v-model="form.ratio">
    <option>9:16</option>
    <option>16:9</option>
    <option>1:1</option>
  </select>
</label>
```

- [ ] **Step 7: Remove genre from frontend API request types**

In `frontend/src/types/api.ts`, remove `genre` from project create/update request types:

```ts
export interface ProjectCreateRequest {
  name: string;
  story: string;
  ratio?: string;
  setup_params?: string[] | null;
}

export interface ProjectUpdateRequest {
  name?: string;
  ratio?: string;
  setup_params?: string[] | null;
}
```

- [ ] **Step 8: Remove genre from scripts and fixtures**

Remove `genre` from every project create request payload that posts to `/api/v1/projects`:

```bash
rg -n '"genre"|genre:' backend/scripts frontend/scripts backend/tests/integration frontend/tests/unit
```

Required edits:

- `backend/scripts/smoke_m1.sh`: remove `"genre":"古风"` from the JSON body.
- `backend/scripts/smoke_m2.sh`: remove `"genre":"科幻"` from the JSON body.
- `frontend/scripts/smoke_m3a.sh`: remove `genre:"古风权谋"` from the `jq -n` create payload.
- `backend/tests/integration/test_projects_api.py`: remove `"genre": "古风"` from the create JSON.
- `backend/tests/integration/test_parse_flow.py`: remove `"genre": "奇幻"` from the create JSON.

Frontend read DTO fixtures may keep a `genre` property because reads still expose model-derived genre, but replace misleading old defaults:

```ts
genre: "现代末世",
```

Apply that to:

- `frontend/tests/unit/character.generate.chain.spec.ts`
- `frontend/tests/unit/workbench.m3a.store.spec.ts`

- [ ] **Step 9: Run focused tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_project_genre_resolution.py -v
```

Expected: pass.

Run:

```bash
cd frontend
npm run typecheck
```

Expected: pass.

- [ ] **Step 10: Commit**

```bash
git add backend/app/tasks/ai/parse_novel.py backend/app/infra/volcano_client.py backend/app/domain/schemas/project.py backend/app/domain/services/project_service.py backend/tests/unit/test_project_genre_resolution.py backend/scripts/smoke_m1.sh backend/scripts/smoke_m2.sh frontend/scripts/smoke_m3a.sh backend/tests/integration/test_projects_api.py backend/tests/integration/test_parse_flow.py frontend/src/views/ProjectCreateView.vue frontend/src/types/api.ts frontend/tests/unit/character.generate.chain.spec.ts frontend/tests/unit/workbench.m3a.store.spec.ts
git commit -m "fix(project): derive genre from model parse"
```

## Task 2: Require Applied Scene Profile Before Scene Style Reference

**Files:**

- Modify: `backend/app/domain/services/style_reference_service.py`
- Modify: `frontend/src/components/scene/SceneAssetsPanel.vue`
- Test: `backend/tests/integration/test_style_reference_api.py`

- [ ] **Step 1: Add failing integration test**

Append to `backend/tests/integration/test_style_reference_api.py`:

```python
import pytest

from app.domain.models import Project


@pytest.mark.asyncio
async def test_scene_style_reference_requires_applied_scene_profile(client, db_session):
    # Test seeding intentionally sets a later stage directly; production stage writes
    # still go through app.pipeline.transitions.
    project = Project(
        name="现代末世",
        story="城市断电,天空裂缝,影形生物入侵。" * 20,
        genre="现代末世",
        stage="characters_locked",
        scene_prompt_profile_draft={"prompt": "现代都市末世夜景", "source": "ai"},
        scene_prompt_profile_applied=None,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    resp = await client.post(f"/api/v1/projects/{project.id}/scene-style-reference/generate")

    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == 40901
    assert "请先确认场景统一视觉设定" in body["message"]
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_style_reference_api.py::test_scene_style_reference_requires_applied_scene_profile -v
```

Expected: fails because scene style reference generation currently does not require applied scene profile.

- [ ] **Step 3: Add backend guard**

In `backend/app/domain/services/style_reference_service.py`, after `assert_asset_editable(project, kind)`:

```python
if kind == "scene" and not (
    isinstance(project.scene_prompt_profile_applied, dict)
    and str(project.scene_prompt_profile_applied.get("prompt") or "").strip()
):
    raise ApiError(40901, "请先确认场景统一视觉设定后再生成场景参考图", http_status=409)
```

- [ ] **Step 4: Disable frontend action until applied**

In `frontend/src/components/scene/SceneAssetsPanel.vue`, compute:

```ts
const canGenerateSceneStyleReference = computed(
  () => flags.value.canEditScenes && current.value?.scenePromptProfile?.status === "applied"
);
```

Use this value for the `StyleReferenceCard` generate disabled state if the card supports it. If the card does not support an explicit disabled prop, guard `handleGenerateStyleReference()`:

```ts
if (current.value?.scenePromptProfile?.status !== "applied") {
  toast.warning("请先确认场景统一视觉设定后再生成场景参考图");
  return;
}
```

- [ ] **Step 5: Run focused checks**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_style_reference_api.py::test_scene_style_reference_requires_applied_scene_profile -v
```

Expected: pass.

Run:

```bash
cd frontend
npm run typecheck
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/services/style_reference_service.py backend/tests/integration/test_style_reference_api.py frontend/src/components/scene/SceneAssetsPanel.vue
git commit -m "fix(generation): require applied scene profile before style reference"
```

## Task 3: Keep Character Style Reference Style-Only and Reduce Over-Copy

**Files:**

- Modify: `backend/app/tasks/ai/prompt_builders.py`
- Modify: `backend/app/tasks/ai/gen_style_reference.py`
- Modify: `backend/app/tasks/ai/gen_character_asset.py`
- Test: `backend/tests/unit/test_generation_prompt_integrity.py`

- [ ] **Step 1: Write prompt integrity tests**

Create `backend/tests/unit/test_generation_prompt_integrity.py`:

```python
from types import SimpleNamespace

from app.tasks.ai.prompt_builders import (
    build_character_headshot_prompt,
    build_character_style_reference_prompt,
    build_scene_asset_prompt,
)


def test_character_style_reference_does_not_include_concrete_character_names():
    project = SimpleNamespace(
        name="末世小说",
        genre="现代末世",
        summary="程序员林川与搭档苏宁在天台对抗影形生物。",
        overview=None,
        story="林川和苏宁在现代都市末世求生。",
        character_prompt_profile_applied={
            "prompt": "现代末世写实漫剧风格,低饱和冷灰光影。角色名林川、苏宁只属于具体角色,不应进入母版。"
        },
    )
    character_names = ["林川", "苏宁"]

    prompt = build_character_style_reference_prompt(project, character_names=character_names)

    assert "林川" not in prompt
    assert "苏宁" not in prompt
    assert "不绑定具体剧情角色" in prompt
    assert "只参考画风" in prompt


def test_headshot_prompt_prioritizes_current_character_identity():
    project = SimpleNamespace(character_prompt_profile_applied={"prompt": "现代末世写实漫剧风格"})
    char = SimpleNamespace(name="林川", summary="普通程序员", description="现代通勤休闲装,紧绷冷静")

    prompt = build_character_headshot_prompt(project, char)

    assert "角色名称：林川" in prompt
    assert "当前角色" in prompt
    assert "不要继承项目级母版示范人物的脸部特征" in prompt


def test_scene_asset_prompt_uses_style_reference_without_copying_layout():
    project = SimpleNamespace(scene_prompt_profile_applied={"prompt": "现代都市末世,断电天台,冷灰低饱和"})
    scene = SimpleNamespace(name="全城断电天台眺望", theme="末世降临", summary="城市断电", description="高楼天台俯瞰现代城区")

    prompt = build_scene_asset_prompt(project, scene)

    assert "现代都市末世" in prompt
    assert "不要直接复制项目级场景母版的具体布局" in prompt
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_generation_prompt_integrity.py -v
```

Expected: fails because current prompt builders include concrete names and do not include style-only wording.

- [ ] **Step 3: Sanitize character style profile input with dynamic names**

In `backend/app/tasks/ai/prompt_builders.py`, add a helper:

```python
def _style_only_character_profile(profile: dict | None, character_names: list[str] | None = None) -> str | None:
    prompt = _profile_prompt(profile)
    if not prompt:
        return None
    blocked_labels = ("角色名称", "角色名", "具体角色")
    blocked_names = [name.strip() for name in (character_names or []) if name and name.strip()]
    lines = [
        line
        for line in str(prompt).splitlines()
        if not any(label in line for label in blocked_labels)
        and not any(name in line for name in blocked_names)
    ]
    return "\n".join(lines).strip() or None
```

Update `build_character_style_reference_prompt()` to accept dynamic names and use this helper instead of `_profile_prompt(...)`:

```python
def build_character_style_reference_prompt(project: Project, *, character_names: list[str] | None = None) -> str:
    profile = _style_only_character_profile(project.character_prompt_profile_applied, character_names)
    ...
```

Do not hard-code project-specific names such as `林川` or `苏宁` in `prompt_builders.py`.

- [ ] **Step 4: Rewrite character style reference prompt**

Update `build_character_style_reference_prompt()` so the generated prompt includes:

```python
"用途：生成项目级角色画风母版,只参考画风、线条、色彩、光影、服装材质和人物比例风格,不绑定具体剧情角色。\n"
"画面要求：中性示范人物,白底或极简浅色背景,正面站姿,单人全身设定图。示范人物不代表任何项目角色。\n"
"继承规则：后续角色图只参考画风和材质质感,不得继承母版示范人物的姓名、身份、脸部特征或剧情关系。\n"
```

Do not add a phrase that bans ancient/court/power-struggle elements.

- [ ] **Step 5: Pass project character names in style reference generation and lower reference stacking**

In `backend/app/tasks/ai/gen_style_reference.py`, before building the project-level character style reference prompt, query current project character names and pass them into `build_character_style_reference_prompt()` when `kind == "character"`:

```python
if kind == "character":
    character_names = [
        str(name).strip()
        for name in (
            await db.execute(select(Character.name).where(Character.project_id == project.id))
        ).scalars().all()
        if str(name).strip()
    ]
    prompt = build_character_style_reference_prompt(project, character_names=character_names)
else:
    prompt = build_scene_style_reference_prompt(project)
```

Add imports in `backend/app/tasks/ai/gen_style_reference.py`:

```python
from sqlalchemy import select
from app.domain.models import Character
```

In `backend/app/tasks/ai/gen_character_asset.py`, replace:

```python
headshot_refs = [url for url in [full_body_url, *(style_refs or [])] if url]
```

with:

```python
headshot_refs = [url for url in [full_body_url] if url]
```

The headshot should inherit identity from the current character full-body image, not the project style mother image. Product impact: headshots no longer directly reference the project style mother image; they inherit style indirectly through the full-body image and prompt profile to reduce face/style over-copy.

- [ ] **Step 6: Clarify style-only scene reference use**

In `build_scene_asset_prompt()`, add positive guidance:

```python
"项目级场景视觉参考图使用规则：只参考整体美术风格、空间质感、色彩光影和材质语言；不要直接复制项目级场景母版的具体布局。当前输出必须以本场景名称、主题、简介和详述为准。\n"
```

Do not add a phrase that bans ancient/court/power-struggle elements.

- [ ] **Step 7: Run tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_generation_prompt_integrity.py -v
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/tasks/ai/prompt_builders.py backend/app/tasks/ai/gen_style_reference.py backend/app/tasks/ai/gen_character_asset.py backend/tests/unit/test_generation_prompt_integrity.py
git commit -m "fix(ai): keep style references style-only"
```

## Task 4: Pass Complete Project Context Into Shot Draft Generation

**Files:**

- Modify: `backend/app/domain/services/shot_draft_service.py`
- Modify: `backend/app/tasks/ai/gen_shot_draft.py`
- Test: `backend/tests/unit/test_generation_prompt_integrity.py`

- [ ] **Step 1: Extend the unit test**

Append to `backend/tests/unit/test_generation_prompt_integrity.py`:

```python
from app.tasks.ai.gen_shot_draft import _build_prompt_messages


def test_shot_draft_messages_include_applied_profiles_and_overview():
    context = {
        "project": {
            "id": "p1",
            "name": "末世小说",
            "genre": "现代末世",
            "ratio": "9:16",
            "summary": "现代城市断电后影形生物入侵。",
            "overview": "当代信息文明崩溃后的现代都市末世。",
            "character_prompt_profile": "现代通勤服装,写实悬疑漫剧风格。",
            "scene_prompt_profile": "现代都市天台,断电城区,冷灰夜景。",
        },
        "shot": {"title": "全城断电", "description": "林川看着现代城区熄灭", "detail": "", "tags": []},
        "skill_prompt": "Seedance prompt rules",
    }

    messages = _build_prompt_messages(context, [])
    joined = "\n".join(item["content"] for item in messages)

    assert "现代末世" in joined
    assert "当代信息文明崩溃后的现代都市末世" in joined
    assert "现代都市天台" in joined
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_generation_prompt_integrity.py::test_shot_draft_messages_include_applied_profiles_and_overview -v
```

Expected: fails because draft messages currently pass only minimal project fields.

- [ ] **Step 3: Add context fields**

In `backend/app/domain/services/shot_draft_service.py`, update the `project` dict returned by `build_generation_context()`:

```python
"project": {
    "id": project.id,
    "name": project.name,
    "genre": project.genre,
    "ratio": project.ratio,
    "summary": project.summary,
    "overview": project.overview,
    "character_prompt_profile": (project.character_prompt_profile_applied or {}).get("prompt"),
    "scene_prompt_profile": (project.scene_prompt_profile_applied or {}).get("prompt"),
},
```

- [ ] **Step 4: Keep prompt generation positive**

In `backend/app/tasks/ai/gen_shot_draft.py`, keep the existing project JSON dump. Add one positive priority statement to the user prompt:

```python
"项目题材、故事概要、项目概览和已应用视觉设定是生成镜头草稿的最高优先级上下文；如果字段之间存在差异,以已应用视觉设定和故事内容为准。\n"
```

Do not add genre-specific negative bans.

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_generation_prompt_integrity.py -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/services/shot_draft_service.py backend/app/tasks/ai/gen_shot_draft.py backend/tests/unit/test_generation_prompt_integrity.py
git commit -m "fix(ai): include applied profiles in shot draft context"
```

## Task 5: Add Backend Job Cancellation

**Files:**

- Modify: `backend/app/api/jobs.py`
- Modify: `backend/app/pipeline/transitions.py`
- Modify: `backend/app/infra/volcano_client.py`
- Modify: `backend/app/tasks/video/render_shot_video.py`
- Modify: `backend/app/tasks/ai/render_shot.py`
- Modify: `backend/app/tasks/ai/gen_character_asset.py`
- Modify: `backend/app/tasks/ai/gen_scene_asset.py`
- Modify: `backend/app/tasks/ai/gen_shot_draft.py`
- Modify: `backend/app/tasks/ai/gen_storyboard.py`
- Modify: `backend/app/tasks/ai/extract_characters.py`
- Modify: `backend/app/tasks/ai/extract_scenes.py`
- Modify: `backend/app/tasks/ai/gen_character_prompt_profile.py`
- Modify: `backend/app/tasks/ai/gen_scene_prompt_profile.py`
- Modify: `backend/app/tasks/ai/gen_style_reference.py`
- Modify: `backend/app/tasks/ai/parse_novel.py`
- Test: `backend/tests/integration/test_job_cancel_api.py`

- [ ] **Step 1: Write cancellation integration tests**

Create `backend/tests/integration/test_job_cancel_api.py`:

```python
import pytest

from app.domain.models import Job
from app.infra.db import get_session_factory
from app.pipeline.transitions import InvalidTransition, update_job_progress


@pytest.mark.asyncio
async def test_cancel_queued_job(client, db_session):
    job = Job(project_id="01H00000000000000000000000", kind="gen_shot_draft", status="queued", progress=0)
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.post(f"/api/v1/jobs/{job.id}/cancel")

    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["id"] == job.id
    assert body["status"] == "canceled"
    await db_session.refresh(job)
    assert job.error_msg is None


@pytest.mark.asyncio
async def test_cancel_succeeded_job_is_conflict(client, db_session):
    job = Job(project_id="01H00000000000000000000000", kind="gen_shot_draft", status="succeeded", progress=100)
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.post(f"/api/v1/jobs/{job.id}/cancel")

    assert resp.status_code == 409
    assert resp.json()["code"] == 40901


@pytest.mark.asyncio
async def test_canceled_job_cannot_be_overwritten_by_stale_worker_session(client, db_session):
    job = Job(project_id="01H00000000000000000000000", kind="gen_shot_draft", status="queued", progress=0)
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # Keep a queued copy in this session's identity map, then cancel from another session.
    await db_session.get(Job, job.id)
    session_factory = get_session_factory()
    async with session_factory() as other:
        await update_job_progress(other, job.id, status="canceled")
        await other.commit()

    with pytest.raises(InvalidTransition):
        await update_job_progress(db_session, job.id, status="running")

    await db_session.refresh(job)
    assert job.status == "canceled"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_job_cancel_api.py -v
```

Expected: fails because the route does not exist.

- [ ] **Step 3: Add provider delete method**

In `backend/app/infra/volcano_client.py`, extend `VolcanoClient`:

```python
async def video_generations_delete(self, task_id: str) -> Any:
    pass
```

In `MockVolcanoClient`:

```python
async def video_generations_delete(self, task_id: str) -> Any:
    return {}
```

In `RealVolcanoClient`:

```python
async def video_generations_delete(self, task_id: str) -> dict:
    return await self._request_with_retry("DELETE", f"/contents/generations/tasks/{task_id}", None)
```

- [ ] **Step 4: Add cancel endpoint**

In `backend/app/api/jobs.py`, add:

```python
from sqlalchemy import select


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = (
        await db.execute(
            select(Job)
            .where(Job.id == job_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not job:
        raise ApiError(40401, "Job 不存在", http_status=404)
    if job.status not in {"queued", "running"}:
        raise ApiError(40901, "只有 queued/running 任务可以取消", http_status=409)

    if job.kind == "render_shot_video":
        payload = job.payload if isinstance(job.payload, dict) else {}
        render_id = payload.get("video_render_id")
        if render_id:
            video = await db.get(ShotVideoRender, render_id)
            if video is not None and video.provider_task_id and video.provider_status == "queued":
                try:
                    await get_volcano_client().video_generations_delete(video.provider_task_id)
                    video.provider_status = "cancelled"
                except Exception:
                    pass

    await update_job_progress(db, job.id, status="canceled")
    await db.commit()
    return ok({"id": job.id, "status": job.status})
```

Import `update_job_progress`, `get_volcano_client`, and `select`.

Provider note: per `docs/huoshan_api/取消或删除视频生成任务.md`, Seedance `DELETE` only cancels provider tasks while provider status is `queued`; `running` is not supported by the current local API docs. Keep the provider call guarded by `video.provider_status == "queued"`, and rely on local cancellation plus worker result suppression for `running`.

- [ ] **Step 5: Refresh job rows before progress transitions**

In `backend/app/pipeline/transitions.py`, change `update_job_progress()` to refresh the job row when loading it:

```python
job = await session.get(Job, job_id, populate_existing=True)
```

This prevents a worker session from using a stale identity-map copy of `queued` after the cancel endpoint has already committed `canceled`.

- [ ] **Step 6: Make workers honor canceled jobs**

Add a shared local helper pattern to each cancelable worker:

```python
async def _is_job_canceled(session, job_id: str) -> bool:
    job = await session.get(Job, job_id, populate_existing=True)
    return job is not None and job.status == "canceled"
```

Use it immediately before every remote provider call and before writing terminal success:

```python
if await _is_job_canceled(session, job_id):
    return
```

Apply checkpoints in:

- `backend/app/tasks/video/render_shot_video.py`: before `update_job_progress(..., status="running")`, before provider create, inside the provider poll loop before each progress write, and before marking succeeded/failed.
- `backend/app/tasks/ai/render_shot.py`: before `update_job_progress(..., status="running")`, before `image_generations()`, before persisting the generated asset, and before marking succeeded/failed.
- `backend/app/tasks/ai/gen_character_asset.py`: before each image generation call and before writing generated URLs.
- `backend/app/tasks/ai/gen_scene_asset.py`: before each image generation call and before writing generated URLs.
- `backend/app/tasks/ai/gen_shot_draft.py`: before each chat completion call and before writing the generated draft.
- `backend/app/tasks/ai/gen_storyboard.py`: before each chat completion call and before inserting generated storyboard rows.
- `backend/app/tasks/ai/extract_characters.py` and `backend/app/tasks/ai/extract_scenes.py`: before chat completion calls, before writing extracted rows, and before dispatching follow-up child jobs.
- `backend/app/tasks/ai/gen_character_prompt_profile.py`, `backend/app/tasks/ai/gen_scene_prompt_profile.py`, and `backend/app/tasks/ai/gen_style_reference.py`: before provider calls and before writing profile/reference outputs.
- `backend/app/tasks/ai/parse_novel.py`: before chat completion and before persisting parse results. If parse is canceled before it chains storyboard generation, do not create the storyboard child job.

Also re-read the job status with `populate_existing=True` before each `update_job_progress(..., status="running" | "succeeded" | "failed")`. If the re-read status is `canceled`, return without calling `update_job_progress`; this prevents `canceled -> running` or `canceled -> failed` `InvalidTransition` exceptions after the cancel endpoint commits.

- [ ] **Step 7: Run tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_job_cancel_api.py -v
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/jobs.py backend/app/pipeline/transitions.py backend/app/infra/volcano_client.py backend/app/tasks/video/render_shot_video.py backend/app/tasks/ai/render_shot.py backend/app/tasks/ai/gen_character_asset.py backend/app/tasks/ai/gen_scene_asset.py backend/app/tasks/ai/gen_shot_draft.py backend/app/tasks/ai/gen_storyboard.py backend/app/tasks/ai/extract_characters.py backend/app/tasks/ai/extract_scenes.py backend/app/tasks/ai/gen_character_prompt_profile.py backend/app/tasks/ai/gen_scene_prompt_profile.py backend/app/tasks/ai/gen_style_reference.py backend/app/tasks/ai/parse_novel.py backend/tests/integration/test_job_cancel_api.py
git commit -m "feat(backend): add job cancellation"
```

## Task 6: Add Frontend Cancel Controls

**Files:**

- Create: `frontend/tests/unit/job-cancel.spec.ts`
- Modify: `frontend/src/api/jobs.ts`
- Modify: `frontend/src/store/workbench.ts`
- Modify: `frontend/src/components/setup/ProjectSetupPanel.vue`
- Modify: `frontend/src/components/character/CharacterAssetsPanel.vue`
- Modify: `frontend/src/components/scene/SceneAssetsPanel.vue`
- Modify: `frontend/src/components/generation/GenerationPanel.vue`
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add API wrapper**

In `frontend/src/api/jobs.ts`, add:

```ts
async cancel(jobId: string): Promise<{ id: string; status: "canceled" }> {
  const r = await client.post(`/jobs/${jobId}/cancel`);
  return r.data;
}
```

- [ ] **Step 2: Add store action**

In `frontend/src/store/workbench.ts`, add:

```ts
async function cancelJob(jobId: string) {
  await jobsApi.cancel(jobId);
  if (parseJob.value?.jobId === jobId) parseJob.value = null;
  if (genStoryboardJob.value?.jobId === jobId) genStoryboardJob.value = null;
  if (generateCharactersJob.value?.jobId === jobId) generateCharactersJob.value = null;
  if (characterPromptProfileJob.value?.jobId === jobId) characterPromptProfileJob.value = null;
  if (characterStyleReferenceJob.value?.jobId === jobId) characterStyleReferenceJob.value = null;
  if (generateScenesJob.value?.jobId === jobId) generateScenesJob.value = null;
  if (scenePromptProfileJob.value?.jobId === jobId) scenePromptProfileJob.value = null;
  if (sceneStyleReferenceJob.value?.jobId === jobId) sceneStyleReferenceJob.value = null;
  if (registerCharacterAssetJob.value?.jobId === jobId) registerCharacterAssetJob.value = null;
  if (renderJob.value?.jobId === jobId) {
    renderJob.value = null;
    activeRenderJobState.value = null;
  }
  for (const [shotId, rec] of Object.entries(draftJobs.value)) {
    if (rec.jobId === jobId) delete draftJobs.value[shotId];
  }
  for (const [key, rec] of Object.entries(regenJobs.value)) {
    if (rec.jobId === jobId) delete regenJobs.value[key];
  }
  await reload({ silent: true });
}
```

Return `cancelJob` from the store.

- [ ] **Step 3: Add cancel button to generation progress**

In `frontend/src/components/generation/GenerationPanel.vue`, inside `.render-progress .progress-head`, add:

```vue
<button class="ghost-btn tiny" type="button" @click="cancelActiveRender">取消生成</button>
```

Add method:

```ts
async function cancelActiveRender() {
  if (!activeRenderJobId.value) return;
  try {
    await store.cancelJob(activeRenderJobId.value);
    toast.warning("已取消生成");
  } catch (e) {
    toast.error(e instanceof ApiError ? messageFor(e.code, e.message) : "取消失败");
  }
}
```

Add equivalent small buttons to setup, character, and scene running banners.

- [ ] **Step 4: Treat canceled as canceled, not failed**

Update all `useJobPolling(..., { onError })` handlers that receive `JobState` so `status === "canceled"` clears local running state and shows a cancellation message instead of storing `error_msg` as a failure:

```ts
if (j?.status === "canceled") {
  toast.warning("已取消生成");
  await store.reload({ silent: true });
  return;
}
```

In `frontend/src/store/workbench.ts`, do not map canceled render queue states to `"failed"`:

```ts
if (status === "canceled") return "pending";
if (status === "failed") return "failed";
```

Add coverage in `frontend/tests/unit/job-cancel.spec.ts` that a canceled polling result does not populate the corresponding `*Error` field.

- [ ] **Step 5: Run frontend checks**

Run:

```bash
cd frontend
npm run typecheck
npm run test
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/jobs.ts frontend/src/store/workbench.ts frontend/src/components/setup/ProjectSetupPanel.vue frontend/src/components/character/CharacterAssetsPanel.vue frontend/src/components/scene/SceneAssetsPanel.vue frontend/src/components/generation/GenerationPanel.vue frontend/src/types/api.ts frontend/tests/unit/job-cancel.spec.ts
git commit -m "feat(frontend): add generation cancel controls"
```

## Task 7: Add Character 360 Turnaround and Voice Metadata

**Files:**

- Create: `backend/alembic/versions/20260428_add_character_turnaround_and_voice.py`
- Modify: `backend/app/domain/models/character.py`
- Modify: `backend/app/domain/schemas/character.py`
- Modify: `backend/app/domain/services/aggregate_service.py`
- Modify: `backend/app/tasks/ai/extract_characters.py`
- Modify: `backend/app/tasks/ai/gen_character_asset.py`
- Modify: `backend/app/tasks/ai/prompt_builders.py`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/components/character/CharacterAssetsPanel.vue`
- Test: `backend/tests/unit/test_generation_prompt_integrity.py`

- [ ] **Step 1: Add model and migration**

In `backend/app/domain/models/character.py`, add:

```python
from sqlalchemy import Boolean

turnaround_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
is_humanoid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
voice_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
voice_reference_audio_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
voice_asset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
```

Create Alembic migration:

```python
"""add character turnaround and voice metadata

Revision ID: 20260428_character_turnaround_voice
Revises: e5f6a7b8c9d0
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20260428_character_turnaround_voice"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("characters", sa.Column("turnaround_image_url", sa.String(length=512), nullable=True))
    op.add_column("characters", sa.Column("is_humanoid", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("characters", sa.Column("voice_profile", sa.JSON(), nullable=True))
    op.add_column("characters", sa.Column("voice_reference_audio_url", sa.String(length=512), nullable=True))
    op.add_column("characters", sa.Column("voice_asset_id", sa.String(length=128), nullable=True))
    op.alter_column("characters", "is_humanoid", server_default=None)


def downgrade() -> None:
    op.drop_column("characters", "voice_asset_id")
    op.drop_column("characters", "voice_reference_audio_url")
    op.drop_column("characters", "voice_profile")
    op.drop_column("characters", "is_humanoid")
    op.drop_column("characters", "turnaround_image_url")
```

- [ ] **Step 2: Add prompt builder for turnaround**

In `backend/app/tasks/ai/prompt_builders.py`, add:

```python
def build_character_turnaround_prompt(project: Project, char: Character) -> str:
    profile = _profile_prompt(project.character_prompt_profile_applied)
    sections: list[str] = []
    if profile:
        sections.append(f"项目级角色画风设定：\n{profile}")
    sections.append(
        f"用途：生成角色 360 度旋转设定图,用于后续视频中保持人物全身造型一致。\n"
        f"角色名称：{char.name}\n"
        f"角色简介：{char.summary or ''}\n"
        f"角色详述：{char.description or ''}\n"
        "画面要求：白底角色转身设定图,同一角色展示正面、三分之二侧面、背面三个角度,服装和发型完全一致,人体比例稳定。\n"
        "禁止项：禁止多人,禁止复杂背景,禁止更换服装,禁止脸部身份漂移,禁止文字水印。"
    )
    return "\n\n".join(sections)
```

- [ ] **Step 3: Generate turnaround for humanoid characters only**

In `backend/app/tasks/ai/extract_characters.py`, extend the model JSON schema and row normalization to include `is_humanoid`:

```python
"name, role_type(protagonist/supporting/atmosphere), is_humanoid(boolean), summary, description。"
```

```python
raw_is_humanoid = item.get("is_humanoid", role_type != "atmosphere")
if isinstance(raw_is_humanoid, str):
    is_humanoid = raw_is_humanoid.strip().lower() in {"true", "1", "yes", "y", "是", "人形"}
else:
    is_humanoid = bool(raw_is_humanoid)
```

Persist:

```python
character.is_humanoid = row["is_humanoid"]
```

In `backend/app/tasks/ai/gen_character_asset.py`, import `build_character_turnaround_prompt`.

Add helper based on the explicit model field, not keyword matching:

```python
def _is_human_character(char: Character) -> bool:
    return bool(char.is_humanoid)
```

After headshot generation:

```python
if _is_human_character(char):
    turnaround_resp = await client.image_generations(
        model=settings.ark_image_model,
        prompt=build_character_turnaround_prompt(project, char),
        references=[build_asset_url(char.full_body_image_url)] if char.full_body_image_url else None,
        n=1,
        size="1344x768",
    )
    turnaround_key = await persist_generated_asset(
        url=_extract_image_url(turnaround_resp),
        project_id=char.project_id,
        kind="character_turnaround",
        ext="png",
    )
    char.turnaround_image_url = turnaround_key
    char.voice_profile = {
        "enabled": True,
        "description": f"{char.name} 的角色声音待配置",
        "source": "placeholder",
    }
```

- [ ] **Step 4: Expose fields**

Add the new fields, including `is_humanoid`, to `CharacterOut`, aggregate character payloads, and frontend types.

- [ ] **Step 5: Update character UI**

In `frontend/src/components/character/CharacterAssetsPanel.vue`, add a third figure for `turnaround_image_url` when present and a voice info article that displays `voice_profile.description` or `暂无角色声音`.

- [ ] **Step 6: Run checks**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_generation_prompt_integrity.py -v
```

Run:

```bash
cd frontend
npm run typecheck
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/20260428_add_character_turnaround_and_voice.py backend/app/domain/models/character.py backend/app/domain/schemas/character.py backend/app/domain/services/aggregate_service.py backend/app/tasks/ai/extract_characters.py backend/app/tasks/ai/gen_character_asset.py backend/app/tasks/ai/prompt_builders.py frontend/src/types/api.ts frontend/src/components/character/CharacterAssetsPanel.vue
git commit -m "feat(character): add turnaround and voice metadata"
```

## Task 8: Enable Video Audio

**Files:**

- Modify: `backend/app/domain/schemas/shot_video.py`
- Modify: `backend/app/domain/services/shot_video_service.py`
- Modify: `backend/app/tasks/video/render_shot_video.py`
- Modify: `backend/app/infra/volcano_client.py`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/shots.ts`
- Modify: `frontend/src/store/workbench.ts`
- Modify: `frontend/src/components/generation/GenerationPanel.vue`
- Test: `backend/tests/integration/test_video_audio_api.py`
- Test: `frontend/tests/unit/video-audio-options.spec.ts`

- [ ] **Step 1: Add backend audio request test**

Create `backend/tests/integration/test_video_audio_api.py`:

```python
from sqlalchemy import select
import pytest

from app.domain.models import Project, ShotVideoRender, StoryboardShot


@pytest.mark.asyncio
async def test_video_submit_persists_generate_audio(client, db_session):
    project = Project(name="p", story="现代末世故事" * 30, genre="现代末世", ratio="9:16", stage="scenes_locked")
    shot = StoryboardShot(project_id=project.id, idx=1, title="断电", description="城市断电", detail="天台")
    db_session.add(project)
    db_session.add(shot)
    await db_session.commit()
    await db_session.refresh(project)
    await db_session.refresh(shot)

    resp = await client.post(
        f"/api/v1/projects/{project.id}/shots/{shot.id}/video",
        json={
            "prompt": "现代城市断电,风声和远处警报声",
            "references": [{"id": "manual:1", "kind": "manual", "name": "ref", "image_url": "https://static.example.com/a.png"}],
            "resolution": "480p",
            "model_type": "fast",
            "generate_audio": True,
        },
    )

    assert resp.status_code == 200
    video = (
        await db_session.execute(
            select(ShotVideoRender).where(ShotVideoRender.shot_id == shot.id)
        )
    ).scalar_one()
    assert video.params_snapshot["generate_audio"] is True
```

- [ ] **Step 2: Extend backend schema**

In `backend/app/domain/schemas/shot_video.py`, add:

```python
generate_audio: bool = True
reference_audio_url: str | None = None
```

- [ ] **Step 3: Persist audio params**

In `backend/app/domain/services/shot_video_service.py`, add `generate_audio` and `reference_audio_url` to `create_video_version()` parameters and set:

```python
"generate_audio": bool(generate_audio),
"reference_audio_url": reference_audio_url,
```

Remove the hard-coded `"generate_audio": False`.

In `backend/app/api/shots.py`, pass request values into the service call:

```python
generate_audio=payload.generate_audio,
reference_audio_url=payload.reference_audio_url,
```

- [ ] **Step 4: Send audio to provider**

In `backend/app/infra/volcano_client.py`, update `video_generations_create()` signature:

```python
reference_audio_url: str | None = None,
```

When present, append:

```python
if reference_audio_url:
    content.append({
        "type": "audio_url",
        "role": "reference_audio",
        "audio_url": {"url": reference_audio_url},
    })
```

In `backend/app/tasks/video/render_shot_video.py`, pass:

```python
reference_audio_url=params.get("reference_audio_url"),
```

- [ ] **Step 5: Add frontend audio toggle**

In `frontend/src/types/api.ts`, extend `ShotVideoSubmitRequest`:

```ts
export interface ShotVideoSubmitRequest {
  prompt: string;
  references: RenderSubmitReference[];
  reference_mentions?: ReferenceMention[];
  duration?: number;
  resolution: ShotVideoResolution;
  model_type: ShotVideoModelType;
  generate_audio?: boolean;
  reference_audio_url?: string | null;
}
```

In `frontend/src/types/index.ts`, extend `VideoGenerationDraft`:

```ts
export interface VideoGenerationDraft {
  prompt: string;
  references: RenderSubmitReference[];
  duration: ShotVideoDurationPreset | null;
  resolution: ShotVideoResolution;
  modelType: ShotVideoModelType;
  generateAudio: boolean;
  referenceAudioUrl: string | null;
}
```

In `frontend/src/store/workbench.ts`, extend the `videoDraftOptions` ref type:

```ts
const videoDraftOptions = ref<Record<string, {
  duration: ShotVideoDurationPreset | null;
  resolution: ShotVideoResolution;
  modelType: ShotVideoModelType;
  generateAudio: boolean;
  referenceAudioUrl: string | null;
}>>({});
```

Initialize `videoDraftOptions` with:

```ts
generateAudio: true,
referenceAudioUrl: null
```

Include it in the video payload:

```ts
generate_audio: options.generateAudio,
reference_audio_url: options.referenceAudioUrl
```

In `frontend/src/components/generation/GenerationPanel.vue`, add a small toggle near model controls:

```vue
<article>
  <span>声音</span>
  <div class="selector-row">
    <button class="ghost-btn small" type="button" :class="{ active: selectedVideoOptions?.generateAudio }" @click="setGenerateAudio(true)">生成声音</button>
    <button class="ghost-btn small" type="button" :class="{ active: !selectedVideoOptions?.generateAudio }" @click="setGenerateAudio(false)">无声</button>
  </div>
</article>
```

Add:

```ts
function setGenerateAudio(value: boolean) {
  if (!selectedRenderShot.value) return;
  store.setVideoDraftOptions(selectedRenderShot.value.shotId, { generateAudio: value });
}
```

- [ ] **Step 6: Run checks**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_video_audio_api.py -v
```

Run:

```bash
cd frontend
npm run typecheck
npm run test
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/domain/schemas/shot_video.py backend/app/domain/services/shot_video_service.py backend/app/tasks/video/render_shot_video.py backend/app/infra/volcano_client.py backend/tests/integration/test_video_audio_api.py frontend/src/types/api.ts frontend/src/api/shots.ts frontend/src/store/workbench.ts frontend/src/components/generation/GenerationPanel.vue frontend/tests/unit/video-audio-options.spec.ts
git commit -m "feat(video): enable audio generation"
```

## Task 9: Current Project Recovery and Verification

**Files:**

- Create: `backend/scripts/derive_project_genre.py`

- [ ] **Step 1: Add one-off model-derived genre repair script**

Create `backend/scripts/derive_project_genre.py`:

```python
import argparse
import asyncio
import json

from app.config import get_settings
from app.domain.models import Project
from app.infra.db import get_session_factory
from app.infra.volcano_client import get_volcano_client
from app.tasks.ai.parse_novel import normalize_parsed_genre
from app.utils.json_utils import extract_json


def _build_prompt(story: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "你是小说题材识别专家,只返回纯 JSON,不包含解释。"},
        {
            "role": "user",
            "content": (
                "请根据小说正文识别短题材标签,返回 JSON: {\"genre\":\"...\"}。\n"
                "genre 应是从正文内容得出的正向题材标签,例如 现代末世、都市悬疑、科幻悬疑、古风权谋。\n"
                "不要沿用已有项目字段,只依据正文判断。\n\n"
                f"小说正文:\n{story[:12000]}"
            ),
        },
    ]


async def derive_project_genre(project_id: str, dry_run: bool) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise SystemExit(f"project not found: {project_id}")

        settings = get_settings()
        client = get_volcano_client()
        resp = await client.chat_completions(
            model=settings.ark_chat_model,
            messages=_build_prompt(project.story or ""),
        )
        content = resp.choices[0].message.content
        data = extract_json(content)
        genre = normalize_parsed_genre(data.get("genre"))
        if not genre:
            raise SystemExit(f"model returned invalid genre: {json.dumps(data, ensure_ascii=False)}")

        print(json.dumps({"id": project.id, "old_genre": project.genre, "new_genre": genre}, ensure_ascii=False))
        if not dry_run:
            project.genre = genre
            await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive and persist project genre from the novel text.")
    parser.add_argument("project_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(derive_project_genre(args.project_id, args.dry_run))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Dry-run current project genre repair**

Run:

```bash
cd backend
./.venv/bin/python scripts/derive_project_genre.py 01KQ91SD9ZZZEXDJB56BVBNTXK --dry-run
```

Expected: the script prints JSON whose `new_genre` is derived from the novel content, for example:

```json
{
  "id": "01KQ91SD9ZZZEXDJB56BVBNTXK",
  "old_genre": "古风权谋",
  "new_genre": "现代末世"
}
```

- [ ] **Step 3: Persist the model-derived current project genre**

Run:

```bash
cd backend
./.venv/bin/python scripts/derive_project_genre.py 01KQ91SD9ZZZEXDJB56BVBNTXK
```

Verify through the API read endpoint only:

```bash
curl -sS http://localhost:8000/api/v1/projects/01KQ91SD9ZZZEXDJB56BVBNTXK | jq '.data | {id,genre,stage_raw}'
```

Expected:

```json
{
  "id": "01KQ91SD9ZZZEXDJB56BVBNTXK",
  "genre": "现代末世",
  "stage_raw": "rendering"
}
```

- [ ] **Step 4: Regenerate dependent assets through the UI**

Use the normal stage rollback flow:

1. Roll back to `characters_locked`.
2. Confirm/apply the scene unified visual profile.
3. Regenerate scene style reference.
4. Regenerate scene assets.
5. Return to rendering.
6. Regenerate affected shot drafts and videos with audio enabled.

- [ ] **Step 5: Backend verification**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/ -v
```

Expected: pass.

Run focused integration tests added by this plan:

```bash
cd backend
./.venv/bin/pytest \
  tests/integration/test_style_reference_api.py \
  tests/integration/test_job_cancel_api.py \
  tests/integration/test_video_audio_api.py \
  -v
```

Expected: pass.

- [ ] **Step 6: Frontend verification**

Run:

```bash
cd frontend
npm run typecheck
npm run test
```

Expected: pass.

- [ ] **Step 7: Smoke verification**

Start the stack through the repo helper:

```bash
script/dev_terminal.sh open
script/dev_terminal.sh send "cd /Users/macbook/Documents/trae_projects/comic-drama-platform && script/start_all.sh"
script/dev_terminal.sh status
```

Then run the relevant smoke scripts:

```bash
cd backend
./scripts/smoke_m2.sh
./scripts/smoke_m3a.sh 01KQ91SD9ZZZEXDJB56BVBNTXK
```

Expected: smoke checks pass or only fail on known external-provider quota/content-filter issues; provider failures must be captured as controlled job failures, not stuck running jobs.

- [ ] **Step 8: Commit verification docs if changed**

If README or docs are updated with new audio/cancel behavior:

```bash
git add backend/README.md frontend/README.md docs/superpowers/plans/2026-04-28-generation-control-audio-and-genre-plan.md
git commit -m "docs(plan): add generation control and audio implementation plan"
```

## Self-Review

- Spec coverage: The plan covers all requested bugs and features: cancellation, style-only character reference, missing character reference generation path, modern-vs-ancient drift via `genre`, reference over-copy, shot draft drift, character full-body/headshot/360/voice, and video audio.
- Prompt constraint: The plan explicitly avoids adding "禁止古风/宫廷/权谋元素" to prompts and instead fixes `genre` and profile application.
- State-machine safety: Stage writes remain in `pipeline/transitions.py`; job status writes must call `update_job_progress`, which refreshes job rows before status transitions so cancellation is not overwritten by stale worker sessions.
- Async invariant: All remote AI operations remain Celery jobs. No HTTP route waits on image/video/audio generation.
- Risk: Per the current local Seedance docs, running provider video tasks cannot be canceled through `DELETE`; the plan handles this as local cancellation plus worker result suppression.

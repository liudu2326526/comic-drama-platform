# Character Role And Visual Type Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split character extraction and asset generation into complete `role_type` and `visual_type` flows so human, stylized human, humanoid monster, creature, anomaly, object, crowd, and environment-force characters use the correct prompts, assets, frontend labels, and Seedance video reference strategy.

**Architecture:** Keep `role_type` as story function and add `visual_type` as the generation routing key. Reuse existing asset columns (`full_body_image_url`, `headshot_image_url`, `turnaround_image_url`) but relabel them by `visual_type`: primary reference, secondary/detail reference, and optional motion reference. Keep stage/job contracts unchanged and route all long-running AI work through existing Celery jobs.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, MySQL enum migrations, Celery, Volcengine Seedance, APIMart GPT-Image-2, Vue 3, Pinia, Vitest, Pytest.

---

## Current State

- `backend/app/domain/models/character.py` has `role_type` with `protagonist/supporting/atmosphere` and `is_humanoid`.
- `backend/app/tasks/ai/extract_characters.py` asks the LLM for `role_type` and `is_humanoid`, but not `visual_type`.
- `backend/app/tasks/ai/prompt_builders.py` only branches on `is_humanoid`, so non-human entities still receive human-adjacent logic too often.
- `backend/app/tasks/ai/gen_character_asset.py` always generates primary full-body image, secondary headshot image, then 360 video when `is_humanoid` is true.
- `backend/app/domain/services/aggregate_service.py` always exposes `full_body/headshot/turnaround` prompt keys and labels are interpreted in the frontend as human assets.
- `frontend/src/components/character/CharacterAssetsPanel.vue` has fixed labels: 全身参考图, 头像参考图, 360 旋转参考视频.

## Target Taxonomy

### `role_type`: story function

```python
CHARACTER_ROLE_VALUES = [
    "lead",
    "supporting",
    "antagonist",
    "atmosphere",
    "crowd",
    "system",
]
```

Compatibility rule: legacy `"protagonist"` input is normalized to `"lead"` before persisting. `role_type="lead"` is the story-role taxonomy value; `is_protagonist` remains the explicit "currently locked protagonist" flag used by the stage transition and UI. Do not fold `is_protagonist` into `role_type` in this plan.

### `visual_type`: generation route

```python
CHARACTER_VISUAL_TYPE_VALUES = [
    "human_actor",
    "stylized_human",
    "humanoid_monster",
    "creature",
    "anomaly_entity",
    "object_entity",
    "crowd_group",
    "environment_force",
]
```

### Asset meaning by visual type

| visual_type | `full_body_image_url` label | `headshot_image_url` label | `turnaround_image_url` label | Portrait library | Voice |
|---|---|---|---|---|---|
| `human_actor` | 全身参考图 | 头像参考图 | 360 旋转参考视频 | Yes, fallback on privacy failure | Yes |
| `stylized_human` | 风格化全身参考图 | 风格化头像参考图 | 360 旋转参考视频 | No by default | Optional placeholder |
| `humanoid_monster` | 类人怪物全身设定图 | 头部/核心局部特写 | 360 展示参考视频 | No | No |
| `creature` | 生物整体设定图 | 核心器官/纹理特写 | 动作参考视频 | No | No |
| `anomaly_entity` | 异常体概念设定图 | 核心符号/粒子形态图 | 动态特效参考视频 | No | No |
| `object_entity` | 物体/终端设定图 | 细节/交互界面图 | 状态变化参考视频 | No | No |
| `crowd_group` | 群体风貌参考图 | Not generated | Not generated | No | No |
| `environment_force` | 环境/灾难源参考图 | 特效/空间异常参考图 | 环境特效参考视频 | No | No |

### Migration and legacy asset note

The `atmosphere + is_humanoid=false -> anomaly_entity` backfill is a one-time best-effort migration for old rows. It may misclassify old `environment_force`, `creature`, or `object_entity` rows because legacy data does not contain enough visual intent. Existing generated assets are not rewritten by this migration; if an old asset was generated with the previous human-style prompts, the user must regenerate that character asset after correcting `visual_type` in the editor.

## Files

- Modify: `backend/app/domain/models/character.py`
- Create: `backend/alembic/versions/20260429_add_character_visual_type_and_roles.py`
- Modify: `backend/app/domain/schemas/character.py`
- Modify: `backend/app/domain/services/character_service.py`
- Modify: `backend/app/domain/services/aggregate_service.py`
- Modify: `backend/app/api/characters.py`
- Modify: `backend/app/pipeline/transitions.py`
- Modify: `backend/app/infra/volcano_client.py`
- Modify: `backend/app/tasks/ai/extract_characters.py`
- Modify: `backend/app/tasks/ai/prompt_builders.py`
- Modify: `backend/app/tasks/ai/gen_character_asset.py`
- Read/verify: `backend/app/tasks/ai/regen_character_assets_batch.py` dispatches child `gen_character_asset` jobs and currently has no human-only prompt logic.
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/character/CharacterAssetsPanel.vue`
- Modify: `frontend/src/components/character/CharacterEditorModal.vue`
- Test: `backend/tests/unit/test_extract_characters_task.py`
- Test: `backend/tests/unit/test_rollback_cascade.py`
- Test: `backend/tests/unit/test_generation_prompt_integrity.py`
- Test: `backend/tests/integration/test_character_dual_image_generation.py`
- Test: `backend/tests/integration/test_shot_reference_api.py`
- Test: `backend/tests/integration/test_m3a_contract.py`
- Test: `backend/tests/integration/test_style_reference_aggregate.py`
- Test: `frontend/tests/unit/character-dual-image-ui.spec.ts`

---

### Task 1: Add `visual_type` and complete `role_type` model support

**Files:**
- Modify: `backend/app/domain/models/character.py`
- Create: `backend/alembic/versions/20260429_add_character_visual_type_and_roles.py`
- Modify: `backend/app/domain/schemas/character.py`
- Modify: `backend/app/pipeline/transitions.py`
- Test: `backend/tests/unit/test_extract_characters_task.py`
- Test: `backend/tests/unit/test_rollback_cascade.py`
- Test: `backend/tests/integration/test_shot_reference_api.py`
- Test: `backend/tests/integration/test_m3a_contract.py`

- [ ] **Step 1: Write model constant tests**

Add to `backend/tests/unit/test_extract_characters_task.py`:

```python
def test_character_role_and_visual_type_constants_cover_generation_routes():
    from app.domain.models.character import CHARACTER_ROLE_VALUES, CHARACTER_VISUAL_TYPE_VALUES

    assert CHARACTER_ROLE_VALUES == [
        "lead",
        "supporting",
        "antagonist",
        "atmosphere",
        "crowd",
        "system",
    ]
    assert CHARACTER_VISUAL_TYPE_VALUES == [
        "human_actor",
        "stylized_human",
        "humanoid_monster",
        "creature",
        "anomaly_entity",
        "object_entity",
        "crowd_group",
        "environment_force",
    ]
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_extract_characters_task.py::test_character_role_and_visual_type_constants_cover_generation_routes -q
```

Expected: fail because `CHARACTER_VISUAL_TYPE_VALUES` does not exist and `CHARACTER_ROLE_VALUES` still contains the legacy set.

- [ ] **Step 3: Update the ORM constants and model**

Modify `backend/app/domain/models/character.py`:

```python
CHARACTER_ROLE_VALUES = [
    "lead",
    "supporting",
    "antagonist",
    "atmosphere",
    "crowd",
    "system",
]

CHARACTER_VISUAL_TYPE_VALUES = [
    "human_actor",
    "stylized_human",
    "humanoid_monster",
    "creature",
    "anomaly_entity",
    "object_entity",
    "crowd_group",
    "environment_force",
]
```

Add the mapped column after `role_type`:

```python
visual_type: Mapped[str] = mapped_column(
    Enum(*CHARACTER_VISUAL_TYPE_VALUES, name="character_visual_type"),
    nullable=False,
    default="human_actor",
)
```

- [ ] **Step 4: Create the Alembic migration**

Create `backend/alembic/versions/20260429_add_character_visual_type_and_roles.py`:

```python
"""add character visual type and expanded roles

Revision ID: 20260429_role_visual
Revises: 20260428_char_turn_voice
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa

revision = "20260429_role_visual"
down_revision = "20260428_char_turn_voice"
branch_labels = None
depends_on = None


ROLE_ENUM_WITH_LEGACY = "ENUM('protagonist','lead','supporting','antagonist','atmosphere','crowd','system')"
ROLE_ENUM_FINAL = "ENUM('lead','supporting','antagonist','atmosphere','crowd','system')"
ROLE_ENUM_DOWN = "ENUM('protagonist','supporting','atmosphere')"
VISUAL_ENUM = (
    "ENUM('human_actor','stylized_human','humanoid_monster','creature',"
    "'anomaly_entity','object_entity','crowd_group','environment_force')"
)


def upgrade() -> None:
    op.execute(f"ALTER TABLE characters MODIFY role_type {ROLE_ENUM_WITH_LEGACY} NOT NULL DEFAULT 'supporting'")
    op.execute("UPDATE characters SET role_type = 'lead' WHERE role_type = 'protagonist'")
    op.execute(f"ALTER TABLE characters MODIFY role_type {ROLE_ENUM_FINAL} NOT NULL DEFAULT 'supporting'")
    op.add_column(
        "characters",
        sa.Column(
            "visual_type",
            sa.Enum(
                "human_actor",
                "stylized_human",
                "humanoid_monster",
                "creature",
                "anomaly_entity",
                "object_entity",
                "crowd_group",
                "environment_force",
                name="character_visual_type",
            ),
            nullable=False,
            server_default="human_actor",
        ),
    )
    # Best-effort legacy backfill. Old rows may need manual visual_type correction in the UI.
    op.execute("UPDATE characters SET visual_type = 'anomaly_entity' WHERE role_type = 'atmosphere' AND is_humanoid = false")
    op.execute(f"ALTER TABLE characters MODIFY visual_type {VISUAL_ENUM} NOT NULL")


def downgrade() -> None:
    op.drop_column("characters", "visual_type")
    op.execute(f"ALTER TABLE characters MODIFY role_type {ROLE_ENUM_WITH_LEGACY} NOT NULL DEFAULT 'supporting'")
    op.execute("UPDATE characters SET role_type = 'protagonist' WHERE role_type = 'lead'")
    op.execute("UPDATE characters SET role_type = 'atmosphere' WHERE role_type IN ('crowd','system')")
    op.execute("UPDATE characters SET role_type = 'supporting' WHERE role_type = 'antagonist'")
    op.execute(f"ALTER TABLE characters MODIFY role_type {ROLE_ENUM_DOWN} NOT NULL DEFAULT 'supporting'")
```

- [ ] **Step 5: Update protagonist locking to use `lead`**

In `backend/app/pipeline/transitions.py`, update `lock_protagonist` so it never writes the removed enum value:

```python
for r in rows:
    if r.id == character.id:
        r.is_protagonist = True
        r.role_type = "lead"
        r.locked = True
        found = True
    else:
        if r.is_protagonist:
            r.is_protagonist = False
            r.role_type = "supporting"

if not found:
    character.is_protagonist = True
    character.role_type = "lead"
    character.locked = True
```

Keep `is_protagonist=True` for the selected locked protagonist. `role_type="lead"` is a story role and must not be treated as a replacement for the `is_protagonist` flag.

- [ ] **Step 6: Update old test fixtures that directly write `protagonist`**

Change direct ORM fixture writes from `role_type="protagonist"` to `role_type="lead"` in:

```text
backend/tests/unit/test_rollback_cascade.py
backend/tests/integration/test_shot_reference_api.py
```

Keep legacy `"protagonist"` only in extraction-normalizer tests where the value is intentionally passed as raw LLM JSON and mapped before ORM persistence.

In `backend/tests/integration/test_m3a_contract.py`, keep the assertion that `is_protagonist` exists in aggregate responses. The contract still exposes the boolean flag even though `role_type` no longer accepts `"protagonist"`.

- [ ] **Step 7: Update backend schemas**

Modify `backend/app/domain/schemas/character.py`:

```python
class CharacterOut(BaseModel):
    id: str
    name: str
    role: str
    role_type: str
    visual_type: str
    is_protagonist: bool
    locked: bool
    summary: str | None
    description: str | None
    meta: list[str] = []
    reference_image_url: str | None
    full_body_image_url: str | None = None
    headshot_image_url: str | None = None
    turnaround_image_url: str | None = None
    is_humanoid: bool = True
    voice_profile: dict[str, Any] | None = None
    voice_reference_audio_url: str | None = None
    voice_asset_id: str | None = None
```

Add to `CharacterUpdate`:

```python
visual_type: str | None = None
```

Change the null rejection loop:

```python
for f in ("name", "role_type", "visual_type"):
    if f in data and data[f] is None:
        raise ValueError(f"{f} 不允许显式 null")
```

- [ ] **Step 8: Run migration and tests**

Run:

```bash
cd backend
./.venv/bin/alembic upgrade head
./.venv/bin/pytest \
  tests/unit/test_extract_characters_task.py::test_character_role_and_visual_type_constants_cover_generation_routes \
  tests/unit/test_rollback_cascade.py \
  tests/integration/test_shot_reference_api.py \
  tests/integration/test_m3a_contract.py \
  -q
```

Expected: migration succeeds and all listed tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/domain/models/character.py backend/app/domain/schemas/character.py backend/app/pipeline/transitions.py backend/alembic/versions/20260429_add_character_visual_type_and_roles.py backend/tests/unit/test_extract_characters_task.py backend/tests/unit/test_rollback_cascade.py backend/tests/integration/test_shot_reference_api.py backend/tests/integration/test_m3a_contract.py
git commit -m "feat(backend): add character role and visual type taxonomy"
```

---

### Task 2: Normalize extracted role and visual types

**Files:**
- Modify: `backend/app/tasks/ai/extract_characters.py`
- Test: `backend/tests/unit/test_extract_characters_task.py`

- [ ] **Step 1: Add normalization tests**

Add to `backend/tests/unit/test_extract_characters_task.py`:

```python
def test_normalize_character_rows_maps_legacy_protagonist_and_visual_type():
    rows = extract_characters_task._normalize_character_rows({
        "characters": [
            {
                "name": "林川",
                "role_type": "protagonist",
                "visual_type": "human_actor",
                "summary": "主角",
                "description": "年龄段：25-30岁；性别气质：沉稳男性；体型轮廓：中等偏瘦；脸部气质：轮廓偏方；发型发色：黑色短碎发；服装层次：蓝色夹克；主色/辅色：藏青/浅灰；鞋履/配件：黑色帆布鞋；唯一辨识点：离线智能手机",
            },
            {
                "name": "异常吞噬暗影",
                "role_type": "antagonist",
                "visual_type": "anomaly_entity",
                "summary": "吞噬生命的异常存在",
                "description": "形态边界：无固定形态；材质/粒子质感：黑雾；颜色光效：黑紫；核心符号：旋涡空洞；变化规律：持续蠕动；空间影响：压暗周围光线；危险感：靠近即吞噬；唯一辨识点：紫色裂纹边缘",
            },
        ]
    })

    assert rows[0]["role_type"] == "lead"
    assert rows[0]["visual_type"] == "human_actor"
    assert rows[0]["is_humanoid"] is True
    assert rows[1]["role_type"] == "antagonist"
    assert rows[1]["visual_type"] == "anomaly_entity"
    assert rows[1]["is_humanoid"] is False
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_extract_characters_task.py::test_normalize_character_rows_maps_legacy_protagonist_and_visual_type -q
```

Expected: fail because `visual_type` is not normalized or returned.

- [ ] **Step 3: Add type constants and helpers to `extract_characters.py`**

Modify imports:

```python
from app.domain.models.character import CHARACTER_ROLE_VALUES, CHARACTER_VISUAL_TYPE_VALUES
```

Replace local valid type logic:

```python
VALID_ROLE_TYPES = set(CHARACTER_ROLE_VALUES)
VALID_VISUAL_TYPES = set(CHARACTER_VISUAL_TYPE_VALUES)
LEGACY_ROLE_ALIASES = {"protagonist": "lead"}
HUMANOID_VISUAL_TYPES = {"human_actor", "stylized_human", "humanoid_monster"}


def _normalize_role_type(value: object) -> str:
    raw = str(value or "supporting").strip() or "supporting"
    raw = LEGACY_ROLE_ALIASES.get(raw, raw)
    return raw if raw in VALID_ROLE_TYPES else "supporting"


def _normalize_visual_type(value: object, *, role_type: str) -> str:
    raw = str(value or "").strip()
    if raw in VALID_VISUAL_TYPES:
        return raw
    if role_type == "crowd":
        return "crowd_group"
    if role_type == "system":
        return "object_entity"
    if role_type == "atmosphere":
        return "anomaly_entity"
    return "human_actor"


def _derive_is_humanoid(visual_type: str) -> bool:
    return visual_type in HUMANOID_VISUAL_TYPES
```

Delete the old `_normalize_bool` helper if it becomes unused after this replacement.

Update `_normalize_character_rows`:

```python
role_type = _normalize_role_type(item.get("role_type"))
visual_type = _normalize_visual_type(item.get("visual_type"), role_type=role_type)
is_humanoid = _derive_is_humanoid(visual_type)
```

Include `visual_type` in the normalized dict. Ignore any raw LLM `is_humanoid` value here; `visual_type` is the source of truth, and `CharacterService.update` applies the same hard override for manual edits.

- [ ] **Step 4: Persist `visual_type`**

In `_upsert_character`, set:

```python
character.role_type = row["role_type"] or "supporting"
character.visual_type = row["visual_type"] or "human_actor"
character.is_humanoid = bool(row.get("is_humanoid", True))
```

- [ ] **Step 5: Run normalization tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_extract_characters_task.py::test_normalize_character_rows_maps_legacy_protagonist_and_visual_type -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/ai/extract_characters.py backend/tests/unit/test_extract_characters_task.py
git commit -m "feat(backend): normalize character visual types"
```

---

### Task 3: Update the extraction prompt to produce type-specific visual descriptions

**Files:**
- Modify: `backend/app/tasks/ai/extract_characters.py`
- Modify: `backend/app/infra/volcano_client.py`
- Test: `backend/tests/unit/test_extract_characters_task.py`

- [ ] **Step 1: Add a prompt-content test**

Extend `test_extract_characters_prompt_requests_unique_visual_descriptions` or add:

```python
@pytest.mark.asyncio
async def test_extract_characters_prompt_requests_role_and_visual_type_templates(
    task_session_factory,
    monkeypatch,
):
    project_id, job_id = await _seed_project_with_job(
        task_session_factory,
        story="天空裂缝中出现异常暗影，程序员林川与前同事苏宁逃离城市。",
    )
    captured: dict[str, str] = {}

    class FakeClient:
        async def chat_completions(self, model, messages):
            captured["prompt"] = messages[0]["content"]

            class Msg:
                content = '[{"name":"林川","role_type":"lead","visual_type":"human_actor","is_humanoid":true,"summary":"主角","description":"年龄段：25-30岁；性别气质：沉稳男性；体型轮廓：中等偏瘦；脸部气质：轮廓偏方；发型发色：黑色短发；服装层次：夹克；主色/辅色：藏青/浅灰；鞋履/配件：黑鞋；唯一辨识点：离线手机"}]'

            class Choice:
                message = Msg()

            class Resp:
                choices = [Choice()]

            return Resp()

    monkeypatch.setattr(extract_characters_task, "get_volcano_client", lambda: FakeClient())
    monkeypatch.setattr(extract_characters_task.gen_character_asset, "delay", lambda *_args: None)

    await extract_characters_task._run(project_id, job_id)

    assert "role_type(lead/supporting/antagonist/atmosphere/crowd/system)" in captured["prompt"]
    assert "visual_type(human_actor/stylized_human/humanoid_monster/creature/anomaly_entity/object_entity/crowd_group/environment_force)" in captured["prompt"]
    assert "人类/风格化人类字段" in captured["prompt"]
    assert "异常体/能量体字段" in captured["prompt"]
    assert "群体角色字段" in captured["prompt"]
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_extract_characters_task.py::test_extract_characters_prompt_requests_role_and_visual_type_templates -q
```

Expected: fail because the prompt does not include `visual_type` and the complete templates.

- [ ] **Step 3: Replace the extraction prompt schema block**

In `backend/app/tasks/ai/extract_characters.py`, replace the existing `prompt` assignment block with:

```python
prompt = (
    "请根据以下小说内容提取其中的主要角色、关键配角、反派、系统型存在、群体角色和氛围/异常存在。\n\n"
    f"小说内容：\n{project.story or ''}\n\n"
    "请以 JSON 数组格式返回，每个对象包含："
    "name, role_type(lead/supporting/antagonist/atmosphere/crowd/system), "
    "visual_type(human_actor/stylized_human/humanoid_monster/creature/anomaly_entity/object_entity/crowd_group/environment_force), "
    "is_humanoid(boolean), summary, description。\n"
    "role_type 只表示剧情功能；visual_type 决定后续如何生成角色形象。"
    "不得因为角色是反派就把 visual_type 写成怪物，必须依据视觉形态判断。\n"
    "summary 用一句话概括角色在故事中的身份/功能；description 必须只写视觉设定，不写剧情地点、剧情动作、世界观解释或环境背景。\n"
    "description 必须按 visual_type 使用以下字段逐项填写具体值，不能只写字段名或要求。\n"
    "人类/风格化人类字段：年龄段；性别气质；体型轮廓；脸部气质；发型发色；服装层次；主色/辅色；鞋履/配件；唯一辨识点。\n"
    "类人怪物字段：整体轮廓；头部/面部结构；身体结构；材质质感；主色/辅色；肢体/运动方式；威胁特征；唯一辨识点。\n"
    "非人生命体字段：整体轮廓；身体结构；材质质感；主色/辅色；运动方式；攻击/交互特征；尺度感；唯一辨识点。\n"
    "异常体/能量体字段：形态边界；材质/粒子质感；颜色光效；核心符号；变化规律；空间影响；危险感；唯一辨识点。\n"
    "物体/系统载体字段：主体结构；材质工艺；交互界面；发光区域；状态变化；尺度/摆放方式；唯一辨识点。\n"
    "群体角色字段：群体构成；整体服装/形态；颜色倾向；数量密度；行动姿态；与场景关系；唯一辨识点。\n"
    "环境力量字段：空间形态；影响范围；材质/气象质感；颜色光效；动态变化；对环境的破坏方式；唯一辨识点。\n"
    "每个角色的发型、服装配色、体型、配件、轮廓和唯一辨识点不得与其他角色重复。"
)
```

- [ ] **Step 4: Update mock provider extraction output**

In `backend/app/infra/volcano_client.py`, update the mock character extraction response so mock-mode smoke covers the new schema and at least one non-human generation route:

```python
content = {
    "characters": [
        {
            "name": "秦昭",
            "role_type": "lead",
            "visual_type": "human_actor",
            "is_humanoid": True,
            "summary": "少年天子",
            "description": "年龄段：十五六岁；性别气质：少年男性；体型轮廓：清瘦；脸部气质：眉眼稚气但神情倔强；发型发色：黑色束发；服装层次：深青窄袖常服外罩短披风；主色/辅色：深青/银灰；鞋履/配件：黑布靴、银灰腰带；唯一辨识点：袖口细金线",
        },
        {
            "name": "江离",
            "role_type": "supporting",
            "visual_type": "human_actor",
            "is_humanoid": True,
            "summary": "摄政王",
            "description": "年龄段：三十岁上下；性别气质：冷峻男性；体型轮廓：高挑肩背挺直；脸部气质：长脸、神情克制；发型发色：乌发整齐束冠；服装层次：玄黑长袍叠深紫外衫；主色/辅色：玄黑/深紫；鞋履/配件：硬底长靴、玉白腰佩；唯一辨识点：左肩暗纹披帛",
        },
        {
            "name": "裂隙黑潮",
            "role_type": "antagonist",
            "visual_type": "anomaly_entity",
            "is_humanoid": False,
            "summary": "从天空裂缝溢出的异常体",
            "description": "形态边界：无固定边缘；材质/粒子质感：黑色烟雾和细碎颗粒；颜色光效：黑紫主光、暗红裂纹；核心符号：中心旋涡空洞；变化规律：持续收缩扩张；空间影响：压暗周围光线；危险感：靠近即吞噬；唯一辨识点：边缘反复闪烁紫红裂纹",
        },
    ]
}
```

- [ ] **Step 5: Run prompt tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_extract_characters_task.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/ai/extract_characters.py backend/app/infra/volcano_client.py backend/tests/unit/test_extract_characters_task.py
git commit -m "feat(backend): extract character visual generation types"
```

---

### Task 4: Refactor character prompt builders around `visual_type`

**Files:**
- Modify: `backend/app/tasks/ai/prompt_builders.py`
- Test: `backend/tests/unit/test_generation_prompt_integrity.py`
- Test: `backend/tests/unit/test_visual_reference_prompts.py`

- [ ] **Step 1: Add prompt-builder tests**

Add to `backend/tests/unit/test_generation_prompt_integrity.py`:

```python
def test_anomaly_entity_prompts_do_not_use_human_fields():
    project = Project(id="p1", name="p", story="story", ratio="9:16")
    char = Character(
        project_id="p1",
        name="异常吞噬暗影",
        role_type="antagonist",
        visual_type="anomaly_entity",
        is_humanoid=False,
        summary="吞噬生命的异常存在",
        description="形态边界：无固定形态；材质/粒子质感：黑雾；颜色光效：黑紫；核心符号：旋涡空洞；变化规律：持续蠕动；空间影响：压暗周围光线；危险感：靠近即吞噬；唯一辨识点：紫色裂纹边缘",
    )

    primary = build_character_full_body_prompt(project, char)
    secondary = build_character_headshot_prompt(project, char)
    motion = build_character_turnaround_prompt(project, char)

    assert "异常体概念设定图" in primary
    assert "核心符号/粒子形态图" in secondary
    assert "动态特效参考视频" in motion
    assert "年龄段" not in primary
    assert "鞋履/配件" not in primary
    assert "头像参考图" not in secondary
    assert "你好,我是角色形象参考" not in motion
    assert "口型同步" not in motion
```

Add:

```python
def test_crowd_group_prompts_skip_secondary_and_motion():
    project = Project(id="p1", name="p", story="story", ratio="9:16")
    char = Character(
        project_id="p1",
        name="普通民众",
        role_type="crowd",
        visual_type="crowd_group",
        is_humanoid=False,
        summary="灾变前的城区普通居民",
        description="群体构成：不同年龄普通居民；整体服装/形态：日常通勤服；颜色倾向：灰蓝低饱和；数量密度：中等密度；行动姿态：惊慌后退；与场景关系：街道背景群体；唯一辨识点：统一携带应急手环",
    )

    primary = build_character_full_body_prompt(project, char)
    assert "群体风貌参考图" in primary
    assert build_character_headshot_prompt(project, char) is None
    assert build_character_turnaround_prompt(project, char) is None
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_generation_prompt_integrity.py::test_anomaly_entity_prompts_do_not_use_human_fields tests/unit/test_generation_prompt_integrity.py::test_crowd_group_prompts_skip_secondary_and_motion -q
```

Expected: fail because prompt builders currently always return strings and only branch on `is_humanoid`.

- [ ] **Step 3: Add visual type helpers**

In `backend/app/tasks/ai/prompt_builders.py`, add:

```python
HUMAN_VISUAL_TYPES = {"human_actor", "stylized_human"}
HUMANOID_MONSTER_VISUAL_TYPES = {"humanoid_monster"}
SECONDARY_REFERENCE_VISUAL_TYPES = {
    "human_actor",
    "stylized_human",
    "humanoid_monster",
    "creature",
    "anomaly_entity",
    "object_entity",
    "environment_force",
}
MOTION_REFERENCE_VISUAL_TYPES = {
    "human_actor",
    "stylized_human",
    "humanoid_monster",
    "creature",
    "anomaly_entity",
    "object_entity",
    "environment_force",
}


def _character_visual_type(char: Character) -> str:
    return str(getattr(char, "visual_type", None) or "human_actor")
```

- [ ] **Step 4: Replace label lists with type-specific fields**

Add dictionaries:

```python
_VISUAL_LABELS_BY_TYPE = {
    "human_actor": ["年龄段", "性别气质", "体型轮廓", "脸部气质", "发型发色", "服装层次", "主色/辅色", "鞋履/配件", "唯一辨识点"],
    "stylized_human": ["年龄段", "性别气质", "体型轮廓", "脸部气质", "发型发色", "服装层次", "主色/辅色", "鞋履/配件", "唯一辨识点"],
    "humanoid_monster": ["整体轮廓", "头部/面部结构", "身体结构", "材质质感", "主色/辅色", "肢体/运动方式", "威胁特征", "唯一辨识点"],
    "creature": ["整体轮廓", "身体结构", "材质质感", "主色/辅色", "运动方式", "攻击/交互特征", "尺度感", "唯一辨识点"],
    "anomaly_entity": ["形态边界", "材质/粒子质感", "颜色光效", "核心符号", "变化规律", "空间影响", "危险感", "唯一辨识点"],
    "object_entity": ["主体结构", "材质工艺", "交互界面", "发光区域", "状态变化", "尺度/摆放方式", "唯一辨识点"],
    "crowd_group": ["群体构成", "整体服装/形态", "颜色倾向", "数量密度", "行动姿态", "与场景关系", "唯一辨识点"],
    "environment_force": ["空间形态", "影响范围", "材质/气象质感", "颜色光效", "动态变化", "对环境的破坏方式", "唯一辨识点"],
}
```

- [ ] **Step 5: Make prompt builders return optional strings**

Change signatures:

```python
def build_character_full_body_prompt(project: Project, char: Character, *, has_reference_image: bool = False) -> str:
    # Keep the existing public API name. This function always returns the primary reference prompt.
    return "\n\n".join(sections)

def build_character_headshot_prompt(project: Project, char: Character, *, has_reference_image: bool = False) -> str | None:
    # Return None when the selected visual_type has no secondary/detail reference.
    return "\n\n".join(sections)

def build_character_turnaround_prompt(
    project: Project,
    char: Character,
    *,
    character_names: list[str] | None = None,
    has_reference_image: bool = False,
) -> str | None:
    # Return None when the selected visual_type has no motion reference.
    return "\n\n".join(sections)
```

For `crowd_group`, `build_character_headshot_prompt` and `build_character_turnaround_prompt` must return `None`.

- [ ] **Step 6: Implement primary prompt routing**

Use this structure in `build_character_full_body_prompt`:

```python
visual_type = _character_visual_type(char)
labels = _VISUAL_LABELS_BY_TYPE.get(visual_type, _VISUAL_LABELS_BY_TYPE["human_actor"])
visual_spec = _visual_spec_block(getattr(char, "description", None), labels)

primary_purpose_by_type = {
    "human_actor": "用途：生成真人/写实人类角色白底全身参考图，用于后续分镜与视频生成的一致性锁定。",
    "stylized_human": "用途：生成风格化人类角色白底全身参考图，用于后续分镜与视频生成的一致性锁定。",
    "humanoid_monster": "用途：生成类人怪物/异变人白底全身设定图，展示完整轮廓、身体结构、材质和威胁特征。",
    "creature": "用途：生成非人生命体整体设定图，展示完整生物轮廓、材质、尺度感和运动特征。",
    "anomaly_entity": "用途：生成异常体概念设定图，展示形态边界、粒子质感、颜色光效和核心符号。",
    "object_entity": "用途：生成物体/系统载体设定图，展示主体结构、材质工艺、交互界面和状态变化。",
    "crowd_group": "用途：生成群体风貌参考图，作为后续分镜中的群体元素引用。",
    "environment_force": "用途：生成环境力量/灾难源参考图，作为后续场景和特效资产引用。",
}
```

Keep the existing reference image rule only when `has_reference_image` is true.

- [ ] **Step 7: Implement secondary prompt routing**

Return `None` for `crowd_group`.

Use purpose labels:

```python
secondary_purpose_by_type = {
    "human_actor": "用途：生成当前真人/写实人类角色白底头像参考图，必须与全身参考图保持同一人物身份、发型、脸型与服装质感。",
    "stylized_human": "用途：生成当前风格化人类角色白底头像参考图，必须与全身参考图保持同一角色身份、发型、脸型与服装质感。",
    "humanoid_monster": "用途：生成当前类人怪物的头部/核心局部特写，必须与全身设定图保持同一材质、轮廓语言和威胁特征。",
    "creature": "用途：生成当前非人生命体的核心器官/爪牙/纹理特写，必须与整体设定图保持同一生物特征。",
    "anomaly_entity": "用途：生成当前异常体的核心符号/粒子形态图，必须与概念设定图保持同一颜色光效和变化规律。",
    "object_entity": "用途：生成当前物体/系统载体的细节/交互界面图，必须与主体设定图保持同一材质工艺和发光区域。",
    "environment_force": "用途：生成当前环境力量的特效/空间异常参考图，必须与灾难源参考图保持同一影响范围和动态变化。",
}
```

- [ ] **Step 8: Implement motion prompt routing**

Return `None` for `crowd_group`.

Keep the existing 360 speech prompt only for `human_actor` and `stylized_human`.

For `humanoid_monster`, return a non-speaking 360 display prompt:

```python
"用途：生成当前类人怪物/异变人 360 度展示参考视频，用于后续视频中保持怪物轮廓、材质和威胁特征一致。\n"
"@图1（全身设定图）作为首帧约束,@图2（头部/核心局部特写）作为细节约束。\n"
"主体原地缓慢完成正面、侧面、背面、另一侧面到正面的展示，不说话，不做真人表演。"
```

For `creature`, return:

```python
"用途：生成当前非人生命体动态动作参考视频，展示运动方式、攻击/交互特征和尺度感。\n"
"参考 @图1（整体设定图）和 @图2（核心局部特写），主体不可变成人形角色，不出现人类五官、鞋履或站姿模板。"
```

For `anomaly_entity`, return:

```python
"用途：生成当前异常体动态特效参考视频，展示形态边界、粒子质感、颜色光效、变化规律和空间影响。\n"
"参考 @图1（异常体概念设定图）和 @图2（核心符号/粒子形态图），主体不得变成人物、怪物或具体动物。"
```

For `object_entity`, return:

```python
"用途：生成当前物体/系统载体状态变化参考视频，展示交互界面、发光区域和状态变化。\n"
"参考 @图1（主体设定图）和 @图2（细节/交互界面图），主体不得拟人化。"
```

For `environment_force`, return:

```python
"用途：生成当前环境力量/灾难源动态特效参考视频，展示影响范围、材质/气象质感、颜色光效和对环境的破坏方式。\n"
"参考 @图1（环境/灾难源参考图）和 @图2（特效/空间异常参考图），画面不得出现具体主角人物。"
```

- [ ] **Step 9: Run prompt tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_generation_prompt_integrity.py tests/unit/test_visual_reference_prompts.py -q
```

Expected: pass.

- [ ] **Step 10: Commit**

```bash
git add backend/app/tasks/ai/prompt_builders.py backend/tests/unit/test_generation_prompt_integrity.py backend/tests/unit/test_visual_reference_prompts.py
git commit -m "feat(backend): route character prompts by visual type"
```

---

### Task 5: Route asset generation by `visual_type`

**Files:**
- Modify: `backend/app/tasks/ai/gen_character_asset.py`
- Test: `backend/tests/integration/test_character_dual_image_generation.py`

- [ ] **Step 1: Add generation branching tests**

Add to `backend/tests/integration/test_character_dual_image_generation.py`:

```python
@pytest.mark.asyncio
async def test_crowd_group_generates_only_primary_reference(db_session, monkeypatch):
    project = Project(name="末世", story="story", ratio="9:16", stage="storyboard_ready")
    db_session.add(project)
    await db_session.flush()
    character = Character(
        project_id=project.id,
        name="普通民众",
        role_type="crowd",
        visual_type="crowd_group",
        is_humanoid=False,
        summary="城区普通居民群体",
        description="群体构成：不同年龄居民；整体服装/形态：日常服装；颜色倾向：灰蓝；数量密度：中等；行动姿态：惊慌后退；与场景关系：街道群体；唯一辨识点：应急手环",
    )
    db_session.add(character)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_character_asset_single", status="queued", target_type="character", target_id=character.id)
    db_session.add(job)
    await db_session.commit()
    image_calls: list[dict] = []
    video_calls: list[dict] = []

    class FakeImageClient:
        async def image_generations(self, model, prompt, **kwargs):
            image_calls.append({"prompt": prompt, **kwargs})
            return {"data": [{"url": "https://volcano.example/crowd.png"}]}

    class FakeVideoClient:
        async def video_generations_create(self, **kwargs):
            video_calls.append(kwargs)
            return {"id": "unexpected"}

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        return f"projects/{project_id}/{kind}/crowd.{ext}"

    task_module = import_module("app.tasks.ai.gen_character_asset")
    monkeypatch.setattr(task_module, "get_character_image_client", lambda: FakeImageClient())
    monkeypatch.setattr(task_module, "get_volcano_client", lambda: FakeVideoClient())
    monkeypatch.setattr(task_module, "persist_generated_asset", fake_persist_generated_asset)

    await run_character_asset_generation(character.id, job.id, session=db_session)

    await db_session.refresh(character)
    await db_session.refresh(job)
    assert job.status == "succeeded"
    assert job.total == 1
    assert job.done == 1
    assert len(image_calls) == 1
    assert video_calls == []
    assert character.full_body_image_url is not None
    assert character.headshot_image_url is None
    assert character.turnaround_image_url is None
```

Add:

```python
@pytest.mark.asyncio
async def test_anomaly_entity_generates_primary_secondary_and_motion_reference(db_session, monkeypatch):
    project = Project(name="末世", story="story", ratio="9:16", stage="storyboard_ready")
    db_session.add(project)
    await db_session.flush()
    character = Character(
        project_id=project.id,
        name="异常吞噬暗影",
        role_type="antagonist",
        visual_type="anomaly_entity",
        is_humanoid=False,
        summary="吞噬生命的异常存在",
        description="形态边界：无固定形态；材质/粒子质感：黑雾；颜色光效：黑紫；核心符号：旋涡空洞；变化规律：持续蠕动；空间影响：压暗周围光线；危险感：靠近即吞噬；唯一辨识点：紫色裂纹边缘",
    )
    db_session.add(character)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_character_asset_single", status="queued", target_type="character", target_id=character.id)
    db_session.add(job)
    await db_session.commit()
    image_calls: list[dict] = []
    video_calls: list[dict] = []

    class FakeImageClient:
        async def image_generations(self, model, prompt, **kwargs):
            image_calls.append({"prompt": prompt, **kwargs})
            return {"data": [{"url": f"https://volcano.example/anomaly-{len(image_calls)}.png"}]}

    class FakeVideoClient:
        async def video_generations_create(self, **kwargs):
            video_calls.append(kwargs)
            return {"id": "video-task-1"}

        async def video_generations_get(self, task_id):
            return {"id": task_id, "status": "succeeded", "content": {"video_url": "https://volcano.example/anomaly.mp4"}}

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        return f"projects/{project_id}/{kind}/{url.rsplit('/', 1)[-1]}.{ext}"

    task_module = import_module("app.tasks.ai.gen_character_asset")
    monkeypatch.setattr(task_module, "get_character_image_client", lambda: FakeImageClient())
    monkeypatch.setattr(task_module, "get_volcano_client", lambda: FakeVideoClient())
    monkeypatch.setattr(task_module, "persist_generated_asset", fake_persist_generated_asset)

    await run_character_asset_generation(character.id, job.id, session=db_session)

    await db_session.refresh(character)
    await db_session.refresh(job)
    assert job.total == 3
    assert job.done == 3
    assert len(image_calls) == 2
    assert len(video_calls) == 1
    assert "动态特效参考视频" in video_calls[0]["prompt"]
    assert character.full_body_image_url is not None
    assert character.headshot_image_url is not None
    assert character.turnaround_image_url is not None
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_character_dual_image_generation.py::test_crowd_group_generates_only_primary_reference tests/integration/test_character_dual_image_generation.py::test_anomaly_entity_generates_primary_secondary_and_motion_reference -q
```

Expected: fail because generation currently always creates a secondary image and only creates motion for `is_humanoid`.

- [ ] **Step 3: Add generation capability helpers**

In `backend/app/tasks/ai/gen_character_asset.py`, add:

```python
SECONDARY_REFERENCE_VISUAL_TYPES = {
    "human_actor",
    "stylized_human",
    "humanoid_monster",
    "creature",
    "anomaly_entity",
    "object_entity",
    "environment_force",
}
MOTION_REFERENCE_VISUAL_TYPES = {
    "human_actor",
    "stylized_human",
    "humanoid_monster",
    "creature",
    "anomaly_entity",
    "object_entity",
    "environment_force",
}
PORTRAIT_LIBRARY_FALLBACK_VISUAL_TYPES = {"human_actor"}
VOICE_PLACEHOLDER_VISUAL_TYPES = {"human_actor"}


def _visual_type(char: Character) -> str:
    return str(getattr(char, "visual_type", None) or "human_actor")


def _expected_asset_steps(visual_type: str, *, secondary_prompt: str | None, motion_prompt: str | None) -> int:
    total = 1
    if visual_type in SECONDARY_REFERENCE_VISUAL_TYPES and secondary_prompt:
        total += 1
    if visual_type in MOTION_REFERENCE_VISUAL_TYPES and motion_prompt:
        total += 1
    return total
```

- [ ] **Step 4: Set job total from the actual visual-type route**

After building `primary_prompt`, `secondary_prompt`, and `motion_prompt`, set the job total before starting provider calls:

```python
expected_steps = _expected_asset_steps(
    visual_type,
    secondary_prompt=secondary_prompt,
    motion_prompt=motion_prompt,
)
await update_job_progress(session, job_id, status="running", total=expected_steps, done=0, progress=0)
await session.commit()
completed_steps = 0
```

After each successfully persisted expected asset, increment the counter and update progress:

```python
completed_steps += 1
await update_job_progress(
    session,
    job_id,
    done=completed_steps,
    total=expected_steps,
    progress=int(completed_steps / expected_steps * 100),
)
await session.commit()
```

This prevents `crowd_group` from reporting a fixed 3-step job even though it only generates one reference image.

- [ ] **Step 5: Gate secondary image generation**

Replace the unconditional headshot generation with:

```python
visual_type = _visual_type(char)
secondary_prompt = build_character_headshot_prompt(
    project,
    char,
    has_reference_image=bool(headshot_refs),
)
if visual_type in SECONDARY_REFERENCE_VISUAL_TYPES and secondary_prompt:
    headshot_resp = await client.image_generations(
        model=image_model,
        prompt=secondary_prompt,
        references=headshot_refs or None,
        n=1,
        size="1024x1024",
    )
    if await is_job_canceled(session, job_id):
        return
    headshot_key = await persist_generated_asset(
        url=_extract_image_url(headshot_resp),
        project_id=char.project_id,
        kind="character_headshot",
        ext="png",
    )
    char.headshot_image_url = headshot_key
else:
    headshot_key = None
    char.headshot_image_url = None
```

- [ ] **Step 6: Gate motion video generation**

Replace `if _is_human_character(char):` with:

```python
motion_prompt = build_character_turnaround_prompt(
    project,
    char,
    character_names=character_names,
    has_reference_image=bool(char.full_body_image_url),
)
if visual_type in MOTION_REFERENCE_VISUAL_TYPES and motion_prompt:
    full_body_url = build_asset_url(char.full_body_image_url)
    headshot_url = build_asset_url(char.headshot_image_url)
    if not full_body_url or not headshot_url:
        raise RuntimeError("生成动态参考视频需要先完成主参考图和细节参考图")
```

For `human_actor` and `stylized_human`, keep the existing first-frame/last-frame call:

```python
image_inputs = [
    {"role": "first_frame", "url": full_body_url},
    {"role": "last_frame", "url": headshot_url},
]
```

For non-human motion references, use reference images:

```python
image_inputs = [
    {"role": "reference_image", "url": full_body_url},
    {"role": "reference_image", "url": headshot_url},
]
```

Only run portrait-library retry when:

```python
if visual_type in PORTRAIT_LIBRARY_FALLBACK_VISUAL_TYPES and _is_reference_privacy_failure(exc):
    full_body_asset_uri, headshot_asset_uri = await _ensure_turnaround_asset_uris(session, char, job_id)
    retry_image_inputs = [
        {"role": "first_frame", "url": full_body_asset_uri},
        {"role": "last_frame", "url": headshot_asset_uri},
    ]
else:
    raise
```

Only set voice placeholder when:

```python
if visual_type in VOICE_PLACEHOLDER_VISUAL_TYPES and not char.voice_profile:
    char.voice_profile = {
        "enabled": True,
        "description": f"{char.name} 的角色声音待配置",
        "source": "placeholder",
    }
```

Do not clear `char.voice_profile` in the non-human branch. Regenerating an asset must not erase a voice the user configured earlier.

- [ ] **Step 7: Run generation tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_character_dual_image_generation.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/tasks/ai/gen_character_asset.py backend/tests/integration/test_character_dual_image_generation.py
git commit -m "feat(backend): generate character assets by visual type"
```

---

### Task 6: Expose type-aware assets through aggregate API

**Files:**
- Modify: `backend/app/domain/services/aggregate_service.py`
- Modify: `backend/app/api/characters.py`
- Modify: `backend/app/domain/schemas/character.py`
- Test: `backend/tests/integration/test_style_reference_aggregate.py`

- [ ] **Step 1: Add aggregate contract test**

Add to `backend/tests/integration/test_style_reference_aggregate.py`:

```python
def test_aggregate_exposes_visual_type_and_type_specific_prompt_labels():
    # Use the existing aggregate test fixture pattern in this file.
    # Seed a Character with visual_type="anomaly_entity".
    # Assert the aggregate character includes visual_type and non-human prompts.
```

Use concrete assertions:

```python
assert saved_character["visual_type"] == "anomaly_entity"
assert "异常体概念设定图" in saved_character["image_prompts"]["full_body"]
assert "核心符号/粒子形态图" in saved_character["image_prompts"]["headshot"]
assert "动态特效参考视频" in saved_character["image_prompts"]["turnaround"]
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_style_reference_aggregate.py::test_aggregate_exposes_visual_type_and_type_specific_prompt_labels -q
```

Expected: fail because aggregate does not expose `visual_type`.

- [ ] **Step 3: Remove legacy `protagonist` compatibility branches from API mappers**

In `backend/app/api/characters.py`, replace `_to_character_out` role normalization with the final role map:

```python
role_cn = {
    "lead": "主角",
    "supporting": "配角",
    "antagonist": "反派",
    "atmosphere": "氛围",
    "crowd": "群体",
    "system": "系统",
}
```

Return `role_type=c.role_type` and `role=role_cn.get(c.role_type, c.role_type)`. Do not keep `"supporting" if c.role_type == "protagonist" else c.role_type`; after the migration this is dead code and hides future enum mistakes.

In `backend/app/domain/services/aggregate_service.py`, update role map:

```python
role_map = {
    "lead": "主角",
    "supporting": "配角",
    "antagonist": "反派",
    "atmosphere": "氛围",
    "crowd": "群体",
    "system": "系统",
}
```

- [ ] **Step 4: Add `visual_type` to character aggregate and remove dead role branches**

In each character dictionary inside the aggregate `characters` list:

```python
"role_type": c.role_type,
"visual_type": c.visual_type,
"role": role_map.get(c.role_type, "配角"),
```

Remove both legacy expressions from the aggregate builder:

```python
"supporting" if c.role_type == "protagonist" else c.role_type
```

Keep image prompt calls, but allow `None` values from prompt builders:

```python
"image_prompts": {
    "full_body": build_character_full_body_prompt(
        project,
        c,
        has_reference_image=bool(project.character_style_reference_image_url),
    ),
    "headshot": build_character_headshot_prompt(
        project,
        c,
        has_reference_image=bool(c.full_body_image_url or c.reference_image_url),
    ),
    "turnaround": build_character_turnaround_prompt(
        project,
        c,
        character_names=character_names,
        has_reference_image=bool(c.full_body_image_url),
    ),
},
```

- [ ] **Step 5: Run aggregate tests**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_style_reference_aggregate.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/services/aggregate_service.py backend/app/api/characters.py backend/app/domain/schemas/character.py backend/tests/integration/test_style_reference_aggregate.py
git commit -m "feat(backend): expose visual type in character aggregate"
```

---

### Task 7: Update frontend types, labels, and visibility rules

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/character/CharacterAssetsPanel.vue`
- Modify: `frontend/src/components/character/CharacterEditorModal.vue`
- Test: `frontend/tests/unit/character-dual-image-ui.spec.ts`

- [ ] **Step 1: Add frontend type tests or UI assertions**

Extend `frontend/tests/unit/character-dual-image-ui.spec.ts` with:

```ts
it("uses visual type labels and hides missing crowd secondary assets", async () => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const store = useWorkbenchStore();
  store.current = {
    id: "p1",
    stage_raw: "storyboard_ready",
    characterPromptProfile: { draft: null, applied: null, status: "empty" },
    characterStyleReference: { imageUrl: null, prompt: null, status: "empty", error: null },
    characters: [
      {
        id: "c-crowd",
        name: "普通民众",
        role: "群体",
        role_type: "crowd",
        visual_type: "crowd_group",
        is_protagonist: false,
        locked: false,
        summary: "城区普通居民群体",
        description: "群体构成：不同年龄居民",
        meta: [],
        reference_image_url: "https://static.example/crowd.png",
        full_body_image_url: "https://static.example/crowd.png",
        headshot_image_url: null,
        turnaround_image_url: null,
        image_prompts: {
          full_body: "群体风貌参考图",
          headshot: null,
          turnaround: null,
        },
      },
    ],
    scenes: [],
    storyboards: [],
  };
  store.selectedCharacterId = "c-crowd";

  const wrapper = mount(CharacterAssetsPanel, { global: { plugins: [pinia], stubs: ["StageRollbackModal"] } });
  expect(wrapper.text()).toContain("群体风貌参考图");
  expect(wrapper.text()).not.toContain("头像参考图");
  expect(wrapper.text()).not.toContain("360 旋转参考视频");
});
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd frontend
npm run test -- character-dual-image-ui.spec.ts
```

Expected: fail because `visual_type` is unknown and labels are fixed.

- [ ] **Step 3: Update frontend TS types**

In `frontend/src/types/api.ts` and `frontend/src/types/index.ts`:

```ts
export type CharacterRoleType = "lead" | "supporting" | "antagonist" | "atmosphere" | "crowd" | "system";

export type CharacterVisualType =
  | "human_actor"
  | "stylized_human"
  | "humanoid_monster"
  | "creature"
  | "anomaly_entity"
  | "object_entity"
  | "crowd_group"
  | "environment_force";
```

Add to `CharacterOut` in `frontend/src/types/api.ts`:

```ts
visual_type?: CharacterVisualType;
```

Add to `CharacterAsset` in `frontend/src/types/index.ts`:

```ts
visual_type?: CharacterVisualType;
```

Add to `CharacterUpdate`:

```ts
visual_type?: CharacterVisualType;
```

- [ ] **Step 4: Add asset label map in `CharacterAssetsPanel.vue`**

Add:

```ts
const CHARACTER_ASSET_LABELS: Record<string, { primary: string; secondary: string | null; motion: string | null }> = {
  human_actor: { primary: "全身参考图", secondary: "头像参考图", motion: "360 旋转参考视频" },
  stylized_human: { primary: "风格化全身参考图", secondary: "风格化头像参考图", motion: "360 旋转参考视频" },
  humanoid_monster: { primary: "类人怪物全身设定图", secondary: "头部/核心局部特写", motion: "360 展示参考视频" },
  creature: { primary: "生物整体设定图", secondary: "核心器官/纹理特写", motion: "动作参考视频" },
  anomaly_entity: { primary: "异常体概念设定图", secondary: "核心符号/粒子形态图", motion: "动态特效参考视频" },
  object_entity: { primary: "物体/终端设定图", secondary: "细节/交互界面图", motion: "状态变化参考视频" },
  crowd_group: { primary: "群体风貌参考图", secondary: null, motion: null },
  environment_force: { primary: "环境/灾难源参考图", secondary: "特效/空间异常参考图", motion: "环境特效参考视频" },
};

const selectedAssetLabels = computed(() => {
  const visualType = selectedCharacter.value?.visual_type ?? "human_actor";
  return CHARACTER_ASSET_LABELS[visualType] ?? CHARACTER_ASSET_LABELS.human_actor;
});
```

Use these labels in the asset cards and prompt accordion labels.

- [ ] **Step 5: Hide unavailable cards**

Update template logic so secondary and motion cards render only when their labels are non-null:

```vue
<div v-if="selectedAssetLabels.secondary" class="asset-image-card">
  <!-- keep the existing secondary image/video body here; only the wrapper condition changes -->
</div>
<div v-if="selectedAssetLabels.motion" class="asset-image-card asset-image-card--wide">
  <!-- keep the existing motion image/video body here; only the wrapper condition changes -->
</div>
```

Keep placeholders only for assets that are actually expected for the selected `visual_type`.

- [ ] **Step 6: Update editor modal**

In `frontend/src/components/character/CharacterEditorModal.vue`, add a visual type select with labels and captions:

```ts
const visualTypeOptions = [
  { value: "human_actor", label: "真人/写实人类", caption: "需要入人像库和真人视频一致性的角色" },
  { value: "stylized_human", label: "风格化人类", caption: "动漫/插画风格的人类角色" },
  { value: "humanoid_monster", label: "类人怪物/异变人", caption: "保持人形轮廓但不按真人人像处理" },
  { value: "creature", label: "非人生命体", caption: "动物、异形、生物怪物等非人角色" },
  { value: "anomaly_entity", label: "异常体/能量体", caption: "黑雾、裂缝、能量团、不可名状异常" },
  { value: "object_entity", label: "物体/系统载体", caption: "终端、道具、系统核心、机械装置" },
  { value: "crowd_group", label: "群体角色", caption: "只生成群体风貌参考图，不生成单体头像和 360 视频" },
  { value: "environment_force", label: "环境力量/灾难源", caption: "灾害源、空间异常、环境特效类存在" },
];
```

Submit `visual_type` in the update payload. After a successful submit, call `store.loadCurrent(projectId)` or update the selected character in store from the API response so the detail card immediately switches to the correct asset labels and expected empty slots.

- [ ] **Step 7: Run frontend tests and typecheck**

Run:

```bash
cd frontend
npm run test -- character-dual-image-ui.spec.ts
npm run typecheck
```

Expected: both pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/types/index.ts frontend/src/components/character/CharacterAssetsPanel.vue frontend/src/components/character/CharacterEditorModal.vue frontend/tests/unit/character-dual-image-ui.spec.ts
git commit -m "feat(frontend): show character assets by visual type"
```

---

### Task 8: Update character update validation and service behavior

**Files:**
- Modify: `backend/app/domain/services/character_service.py`
- Test: `backend/tests/integration/test_prompt_profile_api.py` or `backend/tests/integration/test_character_generate_async_api.py`

- [ ] **Step 1: Add API validation test**

Create or extend an integration test:

```python
@pytest.mark.asyncio
async def test_update_character_accepts_visual_type(client, db_session):
    project = Project(name="p", story="story", ratio="9:16", stage="storyboard_ready")
    db_session.add(project)
    await db_session.flush()
    character = Character(project_id=project.id, name="异常吞噬暗影", role_type="antagonist", visual_type="anomaly_entity")
    db_session.add(character)
    await db_session.commit()

    resp = await client.patch(
        f"/api/v1/projects/{project.id}/characters/{character.id}",
        json={"visual_type": "creature", "role_type": "antagonist"},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["visual_type"] == "creature"
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_character_generate_async_api.py::test_update_character_accepts_visual_type -q
```

Expected: fail because `visual_type` is not handled by current service/API response.

- [ ] **Step 3: Validate update values in `CharacterService.update`**

In `backend/app/domain/services/character_service.py`:

```python
from app.domain.models.character import CHARACTER_ROLE_VALUES, CHARACTER_VISUAL_TYPE_VALUES
```

Add before applying data:

```python
if "role_type" in data and data["role_type"] == "protagonist":
    data["role_type"] = "lead"
if "role_type" in data and data["role_type"] not in CHARACTER_ROLE_VALUES:
    raise ValueError("invalid role_type")
if "visual_type" in data and data["visual_type"] not in CHARACTER_VISUAL_TYPE_VALUES:
    raise ValueError("invalid visual_type")
if data.get("visual_type") in {"creature", "anomaly_entity", "object_entity", "crowd_group", "environment_force"}:
    data["is_humanoid"] = False
elif data.get("visual_type") in {"human_actor", "stylized_human", "humanoid_monster"}:
    data["is_humanoid"] = True
```

Do not mutate `project.stage` here.

- [ ] **Step 4: Run backend integration test**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_character_generate_async_api.py::test_update_character_accepts_visual_type -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/services/character_service.py backend/tests/integration/test_character_generate_async_api.py
git commit -m "feat(backend): update character visual type safely"
```

---

### Task 9: Full verification and local smoke

**Files:**
- No new files unless tests reveal missing fixtures.

- [ ] **Step 1: Run backend focused suite**

Run:

```bash
cd backend
./.venv/bin/pytest \
  tests/unit/test_extract_characters_task.py \
  tests/unit/test_rollback_cascade.py \
  tests/unit/test_generation_prompt_integrity.py \
  tests/unit/test_visual_reference_prompts.py \
  tests/integration/test_character_dual_image_generation.py \
  tests/integration/test_shot_reference_api.py \
  tests/integration/test_m3a_contract.py \
  tests/integration/test_style_reference_aggregate.py \
  tests/integration/test_character_generate_async_api.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run backend lint**

Run:

```bash
cd backend
./.venv/bin/ruff check app tests
```

Expected: `All checks passed!`

- [ ] **Step 3: Run frontend focused suite**

Run:

```bash
cd frontend
npm run test -- character-dual-image-ui.spec.ts character.generate.chain.spec.ts
npm run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 4: Restart backend and workers**

Run through the reusable dev terminal:

```bash
./script/dev_terminal.sh send "cd /Users/macbook/Documents/trae_projects/comic-drama-platform/.worktrees/codex-generation-control-audio-genre && /bin/bash script/stop_all.sh; /bin/bash script/start_all.sh"
```

Expected: `logs/backend.log` shows uvicorn restarted with the new ORM metadata, and `logs/celery_ai.log` / `logs/celery_video.log` show `ready`.

- [ ] **Step 5: Manual smoke with one mixed project**

Use a project story that contains:

- one `human_actor`
- one `stylized_human` or `humanoid_monster`
- one `anomaly_entity`
- one `object_entity`
- one `crowd_group`
- one `environment_force`

Expected after character extraction:

- Frontend list shows all extracted characters.
- Each character detail card shows type-specific labels.
- `crowd_group` shows only 群体风貌参考图.
- `human_actor` shows 全身参考图, 头像参考图, 360 旋转参考视频, and can use portrait-library fallback.
- `anomaly_entity` does not show human fields and does not use portrait-library fallback.

- [ ] **Step 6: Commit verification fixture fixes if needed**

Only if test fixtures needed updates:

```bash
git add backend/tests frontend/tests
git commit -m "test: update character visual type fixtures"
```

---

## Self-Review

- Spec coverage: The plan covers role taxonomy, visual taxonomy, extraction schema, normalization, DB persistence, prompt routing, asset generation routing, aggregate API, frontend labels, editor updates, and verification.
- Placeholder scan: The plan intentionally avoids open-ended implementation steps. The only instruction to reuse an existing fixture is paired with concrete assertions and should be implemented in the named test file following its existing fixture pattern.
- Type consistency: `role_type` values are `lead/supporting/antagonist/atmosphere/crowd/system`; `visual_type` values are `human_actor/stylized_human/humanoid_monster/creature/anomaly_entity/object_entity/crowd_group/environment_force`. These names are used consistently across backend, frontend, and tests.
- Scope check: This is one coherent feature because extraction, prompts, generation, aggregate response, and UI labels are all required to prevent non-human characters from being generated as humans.

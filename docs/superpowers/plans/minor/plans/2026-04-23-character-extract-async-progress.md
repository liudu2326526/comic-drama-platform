# Character Extract Async + Progress Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把角色提取从 `POST /characters/generate` 的同步 HTTP 流程改为独立 Celery 任务,并让前端把“角色提取 → 角色出图”串成一条连续进度条。

**Architecture:** 后端新增 `extract_characters` 主 job 与 Celery task。`POST /characters/generate` 只创建第一段 job 并立即 ack;提取 task 成功后在 worker 内创建第二段 `gen_character_asset` 主 job 及其子 job。前端 store 把这两段都视为“当前角色生成主 job”,通过 `job.result.next_job_id` 无缝切到第二段轮询,并按 `job.kind` 切换进度文案。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / Celery / Redis / MySQL 8 / Vue 3.5 / TypeScript strict / Pinia / Axios / Vitest / pytest-asyncio。

---

## References

- 设计文档: `docs/superpowers/plans/minor/specs/2026-04-23-character-extract-async-design.md`
- 现有后端入口: `backend/app/api/characters.py`
- 现有角色图片任务: `backend/app/tasks/ai/gen_character_asset.py`
- 现有前端角色面板: `frontend/src/components/character/CharacterAssetsPanel.vue`
- 现有前端 store: `frontend/src/store/workbench.ts`

## File Structure

**Create:**

```text
backend/app/tasks/ai/extract_characters.py
backend/tests/integration/test_character_generate_async_api.py
backend/tests/unit/test_extract_characters_task.py
frontend/tests/unit/character.generate.chain.spec.ts
```

**Modify:**

```text
backend/app/domain/models/job.py
backend/alembic/versions/<new_revision>_add_extract_characters_job_kind.py
backend/app/tasks/ai/__init__.py
backend/app/api/characters.py
backend/app/tasks/celery_app.py
backend/README.md
CLAUDE.md
AGENTS.md
frontend/src/api/characters.ts
frontend/src/store/workbench.ts
frontend/src/components/character/CharacterAssetsPanel.vue
frontend/src/types/api.ts
frontend/src/utils/error.ts
frontend/README.md
```

## Task 1: 后端新增 `extract_characters` job kind 与失败测试

**Files:**
- Modify: `backend/app/domain/models/job.py`
- Create: `backend/alembic/versions/<new_revision>_add_extract_characters_job_kind.py`
- Test: `backend/tests/unit/test_extract_characters_task.py`

- [ ] **Step 1: 写 job kind 存在性的失败测试**

```python
from app.domain.models.job import JOB_KIND_VALUES


def test_job_kind_values_contains_extract_characters():
    assert "extract_characters" in JOB_KIND_VALUES
```

- [ ] **Step 2: 运行失败测试**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_extract_characters_task.py -v
```

Expected: FAIL, because `extract_characters` is not present yet.

- [ ] **Step 3: 最小修改 job kind 与新 migration**

```python
# backend/app/domain/models/job.py
JOB_KIND_VALUES = [
    "parse_novel",
    "gen_storyboard",
    "extract_characters",
    "gen_character_asset",
    "gen_character_asset_single",
    "gen_scene_asset",
    "gen_scene_asset_single",
    "register_character_asset",
    "lock_scene_asset",
    "render_shot",
    "render_batch",
    "export_video",
]
```

```python
# backend/alembic/versions/<new_revision>_add_extract_characters_job_kind.py
"""add extract_characters job kind

Revision ID: <new_revision>
Revises: 125f8a6404de
Create Date: 2026-04-23
"""
from typing import Sequence, Union

from alembic import op


revision: str = "<new_revision>"
down_revision: Union[str, None] = "125f8a6404de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE jobs MODIFY COLUMN kind ENUM(
            'parse_novel', 'gen_storyboard', 'extract_characters',
            'gen_character_asset', 'gen_character_asset_single',
            'gen_scene_asset', 'gen_scene_asset_single',
            'register_character_asset', 'lock_scene_asset',
            'render_shot', 'render_batch', 'export_video'
        ) NOT NULL
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE jobs MODIFY COLUMN kind ENUM(
            'parse_novel', 'gen_storyboard',
            'gen_character_asset', 'gen_character_asset_single',
            'gen_scene_asset', 'gen_scene_asset_single',
            'register_character_asset', 'lock_scene_asset',
            'render_shot', 'render_batch', 'export_video'
        ) NOT NULL
    """)
```

```bash
cd backend
alembic revision -m "add extract_characters job kind"
```

- [ ] **Step 4: 重新运行测试**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_extract_characters_task.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/models/job.py backend/alembic/versions/*_add_extract_characters_job_kind.py backend/tests/unit/test_extract_characters_task.py
git commit -m "feat(backend): add extract_characters job kind"
```

## Task 2: `POST /characters/generate` 改为真正立即 ack

**Files:**
- Modify: `backend/app/api/characters.py`
- Test: `backend/tests/integration/test_character_generate_async_api.py`

- [ ] **Step 1: 写 API 失败测试,要求立即返回 extract job**

```python
@pytest.mark.asyncio
async def test_generate_characters_returns_extract_job_ack(client, seeded_storyboard_ready_project):
    pid = seeded_storyboard_ready_project.id

    resp = await client.post(f"/api/v1/projects/{pid}/characters/generate", json={})
    body = resp.json()

    assert resp.status_code == 200
    assert body["code"] == 0
    assert body["data"]["job_id"]
    assert body["data"]["sub_job_ids"] == []
```

- [ ] **Step 2: 运行失败测试**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_character_generate_async_api.py::test_generate_characters_returns_extract_job_ack -v
```

Expected: FAIL after assertions that returned job kind / behavior still does synchronous LLM work.

- [ ] **Step 3: 修改路由,只创建 `extract_characters` job**

```python
# backend/app/api/characters.py
@router.post("/generate", response_model=Envelope[GenerateJobAck])
async def generate_characters(project_id: str, req: CharacterGenerateRequest = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.id == project_id).with_for_update()
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise ApiError(40401, "项目不存在", http_status=404)

    try:
        assert_asset_editable(project, "character")
    except InvalidTransition as e:
        raise ApiError(40301, str(e), http_status=403)

    running_stmt = select(Job).where(
        Job.project_id == project_id,
        Job.kind.in_(["extract_characters", "gen_character_asset"]),
        Job.status.in_(["queued", "running"]),
    )
    existing = (await db.execute(running_stmt)).scalars().first()
    if existing:
        raise ApiError(40901, "已有角色生成任务进行中", http_status=409)

    job = Job(project_id=project_id, kind="extract_characters", status="queued", progress=0, done=0, total=None)
    db.add(job)
    await db.commit()

    from app.tasks.ai.extract_characters import extract_characters
    extract_characters.delay(project_id, job.id)
    return Envelope.success(GenerateJobAck(job_id=job.id, sub_job_ids=[]))
```

- [ ] **Step 4: 重新运行测试**

Run:

```bash
cd backend
./.venv/bin/pytest tests/integration/test_character_generate_async_api.py::test_generate_characters_returns_extract_job_ack -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/characters.py backend/tests/integration/test_character_generate_async_api.py
git commit -m "feat(backend): ack character generation with extract job"
```

## Task 3: 实现 `extract_characters` task 与链式分发

**Files:**
- Create: `backend/app/tasks/ai/extract_characters.py`
- Modify: `backend/app/tasks/ai/__init__.py`
- Modify: `backend/app/tasks/celery_app.py`
- Test: `backend/tests/unit/test_extract_characters_task.py`

- [ ] **Step 1: 写 task 主路径测试**

```python
@pytest.mark.asyncio
async def test_extract_characters_task_creates_next_main_job_and_children(async_session, project_factory, mocker):
    project = await project_factory(stage="storyboard_ready", story="sample story")
    job = Job(project_id=project.id, kind="extract_characters", status="queued", total=None, done=0)
    async_session.add(job)
    await async_session.commit()

    mock_client = mocker.AsyncMock()
    mock_client.chat_completions.return_value = _ChatResponse('[{"name":"秦昭","role_type":"protagonist","summary":"s","description":"d"}]')
    mocker.patch("app.tasks.ai.extract_characters.get_volcano_client", return_value=mock_client)
    mock_delay = mocker.patch("app.tasks.ai.extract_characters.gen_character_asset.delay")

    await _run(project.id, job.id)

    refreshed_job = await async_session.get(Job, job.id)
    assert refreshed_job.status == "succeeded"
    assert refreshed_job.result["next_kind"] == "gen_character_asset"
    assert refreshed_job.result["next_job_id"]
    assert mock_delay.called
```

- [ ] **Step 1.5: 补 dispatch 失败测试**

```python
@pytest.mark.asyncio
async def test_extract_characters_marks_both_jobs_failed_when_dispatch_fails(async_session, project_factory, mocker):
    project = await project_factory(stage="storyboard_ready", story="sample story")
    job = Job(project_id=project.id, kind="extract_characters", status="queued", total=None, done=0)
    async_session.add(job)
    await async_session.commit()

    mock_client = mocker.AsyncMock()
    mock_client.chat_completions.return_value = _ChatResponse('[{"name":"秦昭","role_type":"protagonist","summary":"s","description":"d"}]')
    mocker.patch("app.tasks.ai.extract_characters.get_volcano_client", return_value=mock_client)
    mocker.patch("app.tasks.ai.extract_characters.gen_character_asset.delay", side_effect=RuntimeError("broker down"))

    await _run(project.id, job.id)

    refreshed_job = await async_session.get(Job, job.id)
    assert refreshed_job.status == "failed"
    assert "dispatch failed" in (refreshed_job.error_msg or "")

    parent = (await async_session.execute(select(Job).where(Job.project_id == project.id, Job.kind == "gen_character_asset"))).scalar_one()
    assert parent.status == "failed"
```

- [ ] **Step 2: 运行失败测试**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_extract_characters_task.py::test_extract_characters_task_creates_next_main_job_and_children -v
```

Expected: FAIL because `_run` and `extract_characters` do not exist.

- [ ] **Step 3: 实现 task**

```python
# backend/app/tasks/ai/extract_characters.py
import asyncio
import logging

from sqlalchemy import select

from app.config import get_settings
from app.domain.models import Character, Job, Project
from app.infra import get_volcano_client
from app.infra.db import get_session_factory
from app.pipeline.transitions import update_job_progress
from app.tasks.ai.gen_character_asset import gen_character_asset
from app.utils.json_utils import extract_json
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ai.extract_characters", queue="ai", bind=True)
def extract_characters(self, project_id: str, job_id: str):
    asyncio.run(_run(project_id, job_id))


async def _run(project_id: str, job_id: str) -> None:
    session_factory = get_session_factory()
    settings = get_settings()
    async with session_factory() as session:
        main_job: Job | None = None
        try:
            job = await session.get(Job, job_id)
            if not job:
                return

            await update_job_progress(session, job_id, status="running", progress=10, done=0, total=None)
            await session.commit()

            project = await session.get(Project, project_id)
            if not project:
                await update_job_progress(session, job_id, status="failed", error_msg="项目不存在")
                await session.commit()
                return

            prompt = f"请根据以下小说内容提取其中的主要角色、关键配角和氛围配角。\\n\\n小说内容：\\n{project.story}\\n\\n请以 JSON 数组格式返回，每个对象包含：name, role_type(protagonist/supporting/atmosphere), summary, description。"
            volcano_client = get_volcano_client()
            chat_result = await volcano_client.chat_completions(
                model=settings.ark_chat_model,
                messages=[{"role": "user", "content": prompt}],
            )
            data = extract_json(chat_result.choices[0].message.content)
            rows = data.get("characters", []) if isinstance(data, dict) else data if isinstance(data, list) else []
            if not rows:
                await update_job_progress(session, job_id, status="failed", error_msg="未识别到角色")
                await session.commit()
                return

            await update_job_progress(session, job_id, status="running", progress=45)
            await session.commit()

            character_ids: list[str] = []
            for item in rows:
                stmt = select(Character).where(Character.project_id == project_id, Character.name == item["name"])
                char = (await session.execute(stmt)).scalar_one_or_none()
                if not char:
                    char = Character(
                        project_id=project_id,
                        name=item["name"],
                        role_type=item.get("role_type", "supporting"),
                        summary=item.get("summary"),
                        description=item.get("description"),
                    )
                    session.add(char)
                    await session.flush()
                character_ids.append(char.id)

            await update_job_progress(session, job_id, status="running", progress=70)
            await session.commit()

            main_job = Job(project_id=project_id, kind="gen_character_asset", status="queued", total=len(character_ids), done=0, progress=0)
            session.add(main_job)
            await session.flush()

            child_ids: list[str] = []
            for cid in character_ids:
                child = Job(project_id=project_id, parent_id=main_job.id, kind="gen_character_asset_single", status="queued", progress=0, done=0)
                session.add(child)
                await session.flush()
                child_ids.append(child.id)

            job.result = {
                "next_job_id": main_job.id,
                "next_kind": "gen_character_asset",
                "character_ids": character_ids,
            }
            await session.commit()

            try:
                for cid, jid in zip(character_ids, child_ids, strict=False):
                    gen_character_asset.delay(cid, jid)
            except Exception as exc:
                if main_job is not None:
                    await update_job_progress(session, main_job.id, status="failed", error_msg=f"dispatch failed: {exc}")
                await update_job_progress(session, job_id, status="failed", error_msg=f"dispatch failed: {exc}")
                await session.commit()
                return

            await update_job_progress(session, job_id, status="succeeded", progress=100)
            await session.commit()
        except Exception as exc:
            logger.exception("Error in extract_characters task: %s", exc)
            if main_job is not None and main_job.status in {"queued", "running"}:
                await update_job_progress(session, main_job.id, status="failed", error_msg=str(exc))
            await update_job_progress(session, job_id, status="failed", error_msg=str(exc))
            await session.commit()
```

- [ ] **Step 4: 注册 task 导出**

```python
# backend/app/tasks/ai/__init__.py
from .extract_characters import extract_characters

__all__ = [
    "extract_characters",
    "gen_character_asset",
    "extract_scenes",
    "register_character_asset",
    "lock_scene_asset",
]
```

```python
# backend/app/tasks/celery_app.py
celery_app = Celery(
    "comic_drama",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.ai"],
)
```

- [ ] **Step 5: 运行后端测试**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_extract_characters_task.py tests/integration/test_character_generate_async_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/ai/extract_characters.py backend/app/tasks/ai/__init__.py backend/app/tasks/celery_app.py backend/tests/unit/test_extract_characters_task.py backend/tests/integration/test_character_generate_async_api.py
git commit -m "feat(backend): add extract_characters async chain"
```

## Task 4: 前端把两段 job 串成连续进度

**Files:**
- Modify: `frontend/src/store/workbench.ts`
- Modify: `frontend/src/components/character/CharacterAssetsPanel.vue`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/utils/error.ts`
- Test: `frontend/tests/unit/character.generate.chain.spec.ts`

- [ ] **Step 1: 写 store 恢复逻辑失败测试**

```ts
it("prefers extract_characters over gen_character_asset when both jobs are present", async () => {
  jobsApi.list.mockResolvedValue([
    { id: "job-render", kind: "gen_character_asset", status: "running", progress: 20, created_at: "2026-04-23T00:00:00Z" },
    { id: "job-extract", kind: "extract_characters", status: "running", progress: 45, created_at: "2026-04-23T00:00:01Z" }
  ])

  await store.findAndTrackActiveJobs()

  expect(store.activeGenerateCharactersJobId).toBe("job-extract")
})
```

- [ ] **Step 1.5: 写 timeout 自愈测试**

```ts
it("clears stale generateCharactersError when a running extract_characters job is recovered", async () => {
  store.markGenerateCharactersFailed("timeout of 60000ms exceeded")
  jobsApi.list.mockResolvedValue([
    { id: "job-extract", kind: "extract_characters", status: "running", progress: 45, created_at: "2026-04-23T00:00:01Z" }
  ] as never)

  await store.findAndTrackActiveJobs()

  expect(store.generateCharactersError).toBeNull()
  expect(store.activeGenerateCharactersJobId).toBe("job-extract")
})
```

- [ ] **Step 2: 写面板串联测试**

```ts
it("switches polling target when extract_characters succeeds with next_job_id", async () => {
  const extractJob = { id: "job-a", kind: "extract_characters", status: "succeeded", progress: 100, result: { next_job_id: "job-b", next_kind: "gen_character_asset" } }
  const renderJob = { id: "job-b", kind: "gen_character_asset", status: "running", progress: 33, total: 6, done: 2 }

  // fetcher 第一次回 extract 成功,第二次回 gen_character_asset running
  // 断言 banner 文案先显示“正在提取角色…”,随后切成“正在生成角色… 2/6”
})
```

- [ ] **Step 3: 扩展前端 `JobState.result` 可读 next job**

```ts
// frontend/src/types/api.ts
export interface JobResultPayload {
  next_job_id?: string | null;
  next_kind?: "gen_character_asset" | null;
  character_ids?: string[];
  render_id?: string | null;
}

export interface JobState {
  id: string;
  kind: string;
  status: string;
  progress: number;
  total: number | null;
  done: number;
  result?: JobResultPayload | null;
  error_msg?: string | null;
  created_at: string;
}
```

- [ ] **Step 4: 修改 store 恢复顺序与错误清理**

```ts
// frontend/src/store/workbench.ts
const running = (kind: string) =>
  jobs.find((j: JobState) => j.kind === kind && (j.status === "queued" || j.status === "running"));

if (stage === "storyboard_ready") {
  const extractJob = running("extract_characters");
  const gcJob = running("gen_character_asset");
  if (extractJob) {
    generateCharactersJob.value = { projectId: current.value.id, jobId: extractJob.id };
    generateCharactersError.value = null;
  } else if (gcJob) {
    generateCharactersJob.value = { projectId: current.value.id, jobId: gcJob.id };
    generateCharactersError.value = null;
  } else {
    generateCharactersJob.value = null;
    const failed = lastFailed("extract_characters") ?? lastFailed("gen_character_asset");
    generateCharactersError.value = current.value.characters.length ? null : (failed?.error_msg ?? null);
  }
}
```

- [ ] **Step 5: 修改角色面板串联轮询**

```ts
// frontend/src/components/character/CharacterAssetsPanel.vue
const generateProgressLabel = computed(() => {
  const j = generateJob.value;
  if (!j) return "正在排队…";
  if (j.kind === "extract_characters") return "正在提取角色…";
  if (j.total && j.total > 0) return `正在生成角色… ${j.done}/${j.total}`;
  return `正在生成角色… ${j.progress}%`;
});

useJobPolling(activeGenerateCharactersJobId, {
  onProgress: () => void 0,
  onSuccess: async (job) => {
    const nextJobId = job.result?.next_job_id;
    if (job.kind === "extract_characters" && nextJobId) {
      store.attachGenerateCharactersJob(nextJobId);
      return;
    }
    await store.reload();
    store.markGenerateCharactersSucceeded();
    toast.success("角色已生成");
  },
  onError: (j, err) => {
    const prefix = j?.kind === "extract_characters" ? "角色提取失败" : "角色出图失败";
    const detail = j?.error_msg ?? (err instanceof ApiError ? messageFor(err.code, err.message) : "生成失败");
    const msg = `${prefix}: ${detail}`;
    store.markGenerateCharactersFailed(msg);
    toast.error(msg);
  }
});
```

- [ ] **Step 6: 为 store 增加附着下一个 job 的方法**

```ts
function attachGenerateCharactersJob(jobId: string) {
  if (!current.value) return;
  generateCharactersJob.value = { projectId: current.value.id, jobId };
  generateCharactersError.value = null;
}
```

- [ ] **Step 7: 运行前端测试**

Run:

```bash
cd frontend
npm run test -- character.generate.chain.spec.ts workbench.m3b.store.spec.ts
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/store/workbench.ts frontend/src/components/character/CharacterAssetsPanel.vue frontend/src/types/api.ts frontend/tests/unit/character.generate.chain.spec.ts
git commit -m "feat(frontend): chain extract and character generation progress"
```

## Task 5: 清理超时误报并同步文档

**Files:**
- Modify: `frontend/src/api/characters.ts`
- Modify: `frontend/src/utils/error.ts`
- Modify: `backend/README.md`
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`
- Modify: `frontend/README.md`
- Test: `frontend/tests/unit/characters.api.spec.ts`

- [ ] **Step 1: 调整注释与测试,不再宣称接口“后端立即 ack 角色生成主 job”**

```ts
// frontend/src/api/characters.ts
/**
 * 角色生成返回 extract_characters 主 job,随后前端会自动接续到 gen_character_asset 主 job。
 */
```

```ts
it("generate uses 60s timeout for extract_characters ack request", async () => {
  const spy = vi.spyOn(client, "post").mockResolvedValue({
    data: { job_id: "J1", sub_job_ids: [] }
  } as never);
  await charactersApi.generate("pid", {})
  expect(spy).toHaveBeenCalledWith("/projects/pid/characters/generate", {}, { timeout: 60_000 })
})
```

- [ ] **Step 2: 同步错误码与冲突文案**

```md
<!-- backend/README.md / CLAUDE.md / AGENTS.md -->
| `40901` | 409 | 业务冲突(如同项目已有进行中的角色/场景生成任务) |
```

```ts
// frontend/src/utils/error.ts
[ERROR_CODE.CONFLICT]: "当前已有角色生成任务进行中,请等待完成后再试",
```

- [ ] **Step 3: 在 README 改写旧链路描述,不要只追加一行**

```md
| `POST /api/v1/projects/{id}/characters/generate` | `CharacterAssetsPanel`(空态大按钮)+ `store.generateCharacters`; 返回 `extract_characters` 主 job,前端在其成功后自动续接 `gen_character_asset` 主 job |
```

- [ ] **Step 4: 运行前端文档相关测试**

Run:

```bash
cd frontend
npm run test -- characters.api.spec.ts
```

Expected: PASS, and request-shape assertion now expects `sub_job_ids: []`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/characters.ts frontend/src/utils/error.ts frontend/tests/unit/characters.api.spec.ts frontend/README.md backend/README.md CLAUDE.md AGENTS.md
git commit -m "docs(frontend): describe extract character async chain"
```

## Task 6: 全链路验证

**Files:**
- Verify only

- [ ] **Step 1: 运行后端测试**

Run:

```bash
cd backend
./.venv/bin/pytest tests/unit/test_extract_characters_task.py tests/integration/test_character_generate_async_api.py tests/unit/test_character_service.py -v
```

Expected: PASS.

- [ ] **Step 2: 运行前端测试**

Run:

```bash
cd frontend
npm run test -- characters.api.spec.ts character.generate.chain.spec.ts workbench.m3a.store.spec.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: 手工冒烟**

Run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/projects/<PID>/characters/generate -H 'Content-Type: application/json' -d '{}'
curl -s http://127.0.0.1:8000/api/v1/projects/<PID>/jobs | jq '.data[] | select(.kind=="extract_characters" or .kind=="gen_character_asset") | {id,kind,status,progress,done,total,result,error_msg}'
```

Expected:

- 第一条请求立即返回 `job_id`
- 随后能先看到 `extract_characters`
- 它成功后 `result.next_job_id` 指向 `gen_character_asset`
- 最终 `gen_character_asset` 成功
- `backend/scripts/smoke_m3a.sh` 仍只读取 `.data.job_id`,不依赖 `.data.sub_job_ids[0]`

- [ ] **Step 4: Commit**

```bash
git status --short
```

Expected: clean working tree.

## Self-Review

- Spec coverage:
  - 角色提取异步化: Task 2 + Task 3
  - 两段进度串联: Task 4
  - timeout 误报收敛: Task 4 + Task 5
- Placeholder scan:
  - 已给出新增文件、代码片段、命令、预期结果
- Type consistency:
  - 前端通过 `job.result.next_job_id`
  - 后端 `extract_characters` 写同名字段
  - `next_kind` 用 `"gen_character_asset" | null` 而不是宽泛 `string`

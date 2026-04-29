import importlib
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.models import Character, Job
from app.domain.models.job import JOB_KIND_VALUES
extract_characters_task = importlib.import_module("app.tasks.ai.extract_characters")


def _chat_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


async def _create_extract_job(db_session, project_id: str) -> Job:
    job = Job(
        project_id=project_id,
        kind="extract_characters",
        status="queued",
        progress=0,
        done=0,
        total=None,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


async def _load_characters(session_factory, project_id: str) -> list[Character]:
    async with session_factory() as session:
        return (
            await session.execute(
                select(Character)
                .where(Character.project_id == project_id)
                .order_by(Character.created_at, Character.id)
            )
        ).scalars().all()


async def _load_jobs(session_factory, project_id: str) -> list[Job]:
    async with session_factory() as session:
        return (
            await session.execute(
                select(Job).where(Job.project_id == project_id).order_by(Job.created_at, Job.id)
            )
        ).scalars().all()


def test_job_kind_values_contains_extract_characters():
    assert "extract_characters" in JOB_KIND_VALUES


@pytest.fixture
def task_session_factory(test_engine, monkeypatch):
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr(extract_characters_task, "get_session_factory", lambda: factory)
    return factory


@pytest.mark.asyncio
async def test_extract_characters_task_creates_next_main_job_and_children(
    db_session,
    task_session_factory,
    project_factory,
    monkeypatch,
):
    project = await project_factory(
        stage="storyboard_ready",
        story="林夏在雨夜遇见周沉，两人一起追查剧院旧案。",
    )
    project_id = project.id
    existing = Character(
        project_id=project_id,
        name="林夏",
        role_type="supporting",
        summary="旧摘要",
        description="旧描述",
    )
    stale = Character(
        project_id=project_id,
        name="旧角色",
        role_type="supporting",
        summary="应被替换",
        description="旧抽取残留",
    )
    db_session.add_all([existing, stale])
    await db_session.commit()
    await db_session.refresh(existing)
    job = await _create_extract_job(db_session, project_id)
    existing_id = existing.id
    job_id = job.id
    dispatched: list[tuple[str, str, bool]] = []

    class FakeClient:
        async def chat_completions(self, model: str, messages: list[dict], **kwargs):
            assert model == "test-chat-model"
            assert messages
            return _chat_response(
                """
                [
                  {"name": "林夏", "role_type": "protagonist", "summary": "女主", "description": "敏锐记者"},
                  {"name": "周沉", "role_type": "supporting", "summary": "男主搭档", "description": "冷静刑警"}
                ]
                """
            )

    def fake_delay(character_id: str, child_job_id: str, replace_existing: bool = False) -> None:
        dispatched.append((character_id, child_job_id, replace_existing))

    monkeypatch.setattr(
        extract_characters_task,
        "get_settings",
        lambda: SimpleNamespace(ark_chat_model="test-chat-model"),
    )
    monkeypatch.setattr(
        extract_characters_task,
        "get_volcano_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(extract_characters_task.gen_character_asset, "delay", fake_delay)

    await extract_characters_task._run(project_id, job_id)

    jobs = await _load_jobs(task_session_factory, project_id)
    characters = await _load_characters(task_session_factory, project_id)

    extract_job = next(item for item in jobs if item.id == job_id)
    next_job = next(item for item in jobs if item.kind == "gen_character_asset")
    child_jobs = [item for item in jobs if item.parent_id == next_job.id]

    assert extract_job.status == "succeeded"
    assert extract_job.progress == 100
    assert extract_job.total is None
    assert extract_job.result == {
        "next_job_id": next_job.id,
        "next_kind": "gen_character_asset",
        "character_ids": [character.id for character in characters],
    }

    assert next_job.status == "running"
    assert next_job.progress == 0
    assert next_job.done == 0
    assert next_job.total == 2

    assert len(characters) == 2
    assert {item.name for item in characters} == {"林夏", "周沉"}
    assert len(child_jobs) == 2
    assert all(item.kind == "gen_character_asset_single" for item in child_jobs)
    assert all(item.status == "queued" for item in child_jobs)

    lin_xia = next(item for item in characters if item.name == "林夏")
    assert lin_xia.id == existing_id
    assert lin_xia.role_type == "supporting"
    assert lin_xia.summary == "女主"
    assert lin_xia.description == "敏锐记者"

    assert {item[0] for item in dispatched} == {character.id for character in characters}
    assert {item[1] for item in dispatched} == {child_job.id for child_job in child_jobs}
    assert all(item[2] is True for item in dispatched)


@pytest.mark.asyncio
async def test_extract_characters_prompt_requests_unique_visual_descriptions(
    db_session,
    task_session_factory,
    project_factory,
    monkeypatch,
):
    project = await project_factory(
        stage="storyboard_ready",
        story="林川和苏宁在现代城市灾变中逃生。",
    )
    project_id = project.id
    job = await _create_extract_job(db_session, project_id)
    captured_messages: list[dict] = []

    class FakeClient:
        async def chat_completions(self, model: str, messages: list[dict], **kwargs):
            captured_messages.extend(messages)
            return _chat_response(
                """
                [
                  {
                    "name": "林川",
                    "role_type": "supporting",
                    "is_humanoid": true,
                    "summary": "普通程序员",
                    "description": "二十多岁清瘦男性,黑色短碎发,灰黑工装夹克,旧运动鞋,袖口磨损,神情紧绷"
                  }
                ]
                """
            )

    monkeypatch.setattr(
        extract_characters_task,
        "get_settings",
        lambda: SimpleNamespace(ark_chat_model="test-chat-model"),
    )
    monkeypatch.setattr(extract_characters_task, "get_volcano_client", lambda: FakeClient())
    monkeypatch.setattr(extract_characters_task.gen_character_asset, "delay", lambda *_args: None)

    await extract_characters_task._run(project_id, job.id)

    prompt = captured_messages[0]["content"]
    assert "description 必须是角色视觉描述" in prompt
    assert "description 必须按以下格式逐项填写具体值" in prompt
    assert "年龄段：具体年龄段" in prompt
    assert "唯一辨识点：具体且不可与其他角色重复" in prompt
    assert "年龄段" in prompt
    assert "体型轮廓" in prompt
    assert "发型发色" in prompt
    assert "服装层次" in prompt
    assert "主色/辅色" in prompt
    assert "唯一辨识点" in prompt
    assert "不得与其他角色重复" in prompt
    assert "不要写剧情地点" in prompt


@pytest.mark.asyncio
async def test_extract_characters_marks_both_jobs_failed_when_dispatch_fails(
    db_session,
    task_session_factory,
    project_factory,
    monkeypatch,
):
    project = await project_factory(
        stage="storyboard_ready",
        story="秦昭回到故乡，重新面对家族旧案。",
    )
    project_id = project.id
    job = await _create_extract_job(db_session, project_id)
    job_id = job.id

    class FakeClient:
        async def chat_completions(self, model: str, messages: list[dict], **kwargs):
            return _chat_response(
                """
                [{"name": "秦昭", "role_type": "protagonist", "summary": "归乡者", "description": "执拗调查员"}]
                """
            )

    monkeypatch.setattr(
        extract_characters_task,
        "get_settings",
        lambda: SimpleNamespace(ark_chat_model="test-chat-model"),
    )
    monkeypatch.setattr(
        extract_characters_task,
        "get_volcano_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        extract_characters_task.gen_character_asset,
        "delay",
        lambda character_id, child_job_id, replace_existing=False: (_ for _ in ()).throw(RuntimeError("broker down")),
    )

    await extract_characters_task._run(project_id, job_id)

    jobs = await _load_jobs(task_session_factory, project_id)
    extract_job = next(item for item in jobs if item.id == job_id)
    next_job = next(item for item in jobs if item.kind == "gen_character_asset")

    assert extract_job.status == "failed"
    assert extract_job.error_msg is not None
    assert "dispatch failed:" in extract_job.error_msg
    assert "broker down" in extract_job.error_msg

    assert next_job.status == "failed"
    assert next_job.error_msg is not None
    assert "dispatch failed:" in next_job.error_msg
    assert "broker down" in next_job.error_msg


@pytest.mark.asyncio
async def test_extract_characters_cleans_derived_jobs_when_canceled_before_dispatch(
    db_session,
    task_session_factory,
    project_factory,
    monkeypatch,
):
    project = await project_factory(
        stage="storyboard_ready",
        story="林川和苏宁在现代城市灾变中逃生。",
    )
    project_id = project.id
    job = await _create_extract_job(db_session, project_id)
    job_id = job.id
    cancel_checks = 0
    dispatched: list[tuple[str, str, bool]] = []

    class FakeClient:
        async def chat_completions(self, model: str, messages: list[dict], **kwargs):
            return _chat_response(
                """
                [
                  {"name": "林川", "role_type": "supporting", "summary": "程序员", "description": "青年男性"},
                  {"name": "苏宁", "role_type": "supporting", "summary": "同事", "description": "短发女性"}
                ]
                """
            )

    async def fake_is_job_canceled(session, checked_job_id: str) -> bool:
        nonlocal cancel_checks
        cancel_checks += 1
        if cancel_checks >= 3:
            checked_job = await session.get(Job, checked_job_id)
            if checked_job is not None:
                checked_job.status = "canceled"
            return True
        return False

    monkeypatch.setattr(
        extract_characters_task,
        "get_settings",
        lambda: SimpleNamespace(ark_chat_model="test-chat-model"),
    )
    monkeypatch.setattr(extract_characters_task, "get_volcano_client", lambda: FakeClient())
    monkeypatch.setattr(extract_characters_task, "is_job_canceled", fake_is_job_canceled)
    monkeypatch.setattr(
        extract_characters_task.gen_character_asset,
        "delay",
        lambda character_id, child_job_id, replace_existing=False: dispatched.append(
            (character_id, child_job_id, replace_existing)
        ),
    )

    await extract_characters_task._run(project_id, job_id)

    jobs = await _load_jobs(task_session_factory, project_id)
    characters = await _load_characters(task_session_factory, project_id)
    extract_job = next(item for item in jobs if item.id == job_id)
    next_job = next(item for item in jobs if item.kind == "gen_character_asset")
    child_jobs = [item for item in jobs if item.parent_id == next_job.id]

    assert extract_job.status == "canceled"
    assert next_job.status == "canceled"
    assert all(item.status == "canceled" for item in child_jobs)
    assert characters == []
    assert dispatched == []


@pytest.mark.asyncio
async def test_extract_characters_fails_when_no_characters_are_detected(
    db_session,
    task_session_factory,
    project_factory,
    monkeypatch,
):
    project = await project_factory(
        stage="storyboard_ready",
        story="这一段只有空镜和环境描写，没有明确人物。",
    )
    project_id = project.id
    job = await _create_extract_job(db_session, project_id)
    job_id = job.id

    class FakeClient:
        async def chat_completions(self, model: str, messages: list[dict], **kwargs):
            return _chat_response("[]")

    monkeypatch.setattr(
        extract_characters_task,
        "get_settings",
        lambda: SimpleNamespace(ark_chat_model="test-chat-model"),
    )
    monkeypatch.setattr(
        extract_characters_task,
        "get_volcano_client",
        lambda: FakeClient(),
    )

    await extract_characters_task._run(project_id, job_id)

    jobs = await _load_jobs(task_session_factory, project_id)
    extract_job = next(item for item in jobs if item.id == job_id)

    assert extract_job.status == "failed"
    assert extract_job.error_msg == "未识别到角色"
    assert extract_job.total is None
    assert [item for item in jobs if item.kind == "gen_character_asset"] == []

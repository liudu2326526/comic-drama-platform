import pytest
from importlib import import_module

from app.domain.models import Character, Job, Project
from app.tasks.ai.gen_character_asset import run_character_asset_generation


@pytest.mark.asyncio
async def test_character_asset_generation_writes_full_body_and_headshot(db_session, monkeypatch):
    project = Project(
        name="雨夜",
        story="story",
        ratio="9:16",
        stage="storyboard_ready",
        character_style_reference_image_url="projects/p/style/ref.png",
    )
    db_session.add(project)
    await db_session.flush()
    character = Character(project_id=project.id, name="秦昭", role_type="supporting", summary="少年天子")
    db_session.add(character)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_character_asset_single", status="queued", target_type="character", target_id=character.id)
    db_session.add(job)
    await db_session.commit()
    calls: list[dict] = []

    class FakeClient:
        async def image_generations(self, model, prompt, **kwargs):
            calls.append({"prompt": prompt, **kwargs})
            return {"data": [{"url": f"https://volcano.example/tmp-{len(calls)}.png"}]}

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        return f"projects/{project_id}/{kind}/{url.rsplit('-', 1)[-1]}"

    task_module = import_module("app.tasks.ai.gen_character_asset")
    monkeypatch.setattr(task_module, "get_volcano_client", lambda: FakeClient())
    monkeypatch.setattr(task_module, "persist_generated_asset", fake_persist_generated_asset)

    await run_character_asset_generation(character.id, job.id, session=db_session)

    await db_session.refresh(character)
    await db_session.refresh(job)
    assert character.full_body_image_url and "/character_full_body/" in character.full_body_image_url
    assert character.reference_image_url == character.full_body_image_url
    assert character.headshot_image_url and "/character_headshot/" in character.headshot_image_url
    assert "全身参考图" in calls[0]["prompt"]
    assert "头像参考图" in calls[1]["prompt"]
    assert calls[0]["references"][0].endswith("/style/ref.png")
    assert calls[1]["references"][0].endswith("/character_full_body/1.png")
    assert job.status == "succeeded"


@pytest.mark.asyncio
async def test_character_asset_generation_marks_parent_failed_when_child_fails(
    db_session,
    monkeypatch,
):
    project = Project(
        name="雨夜",
        story="story",
        ratio="9:16",
        stage="storyboard_ready",
    )
    db_session.add(project)
    await db_session.flush()
    character = Character(
        project_id=project.id,
        name="赵衡",
        role_type="supporting",
        summary="旧案真凶",
    )
    db_session.add(character)
    await db_session.flush()
    parent_job = Job(
        project_id=project.id,
        kind="gen_character_asset",
        status="running",
        progress=0,
        done=0,
        total=1,
    )
    db_session.add(parent_job)
    await db_session.flush()
    child_job = Job(
        project_id=project.id,
        parent_id=parent_job.id,
        kind="gen_character_asset_single",
        status="queued",
        target_type="character",
        target_id=character.id,
    )
    db_session.add(child_job)
    await db_session.commit()

    class FakeClient:
        async def image_generations(self, model, prompt, **kwargs):
            raise RuntimeError("InputTextSensitiveContentDetected")

    task_module = import_module("app.tasks.ai.gen_character_asset")
    monkeypatch.setattr(task_module, "get_volcano_client", lambda: FakeClient())

    await run_character_asset_generation(character.id, child_job.id, session=db_session)

    await db_session.refresh(parent_job)
    await db_session.refresh(child_job)
    assert child_job.status == "failed"
    assert parent_job.status == "failed"
    assert parent_job.done == 1
    assert parent_job.error_msg is not None
    assert "InputTextSensitiveContentDetected" in parent_job.error_msg

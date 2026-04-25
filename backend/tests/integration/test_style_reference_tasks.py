import pytest

from app.domain.models import Job, Project
from app.tasks.ai.gen_style_reference import run_character_style_reference, run_scene_style_reference


class FakeImageClient:
    def __init__(self):
        self.calls: list[dict] = []

    async def image_generations(self, model, prompt, **kwargs):
        self.calls.append({"model": model, "prompt": prompt, **kwargs})
        return {"data": [{"url": "https://volcano.example/tmp.png"}]}


@pytest.mark.asyncio
async def test_character_style_reference_task_persists_project_state(db_session, monkeypatch):
    project = Project(name="雨夜", story="story", ratio="9:16", stage="storyboard_ready")
    db_session.add(project)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_character_style_reference", status="queued")
    db_session.add(job)
    await db_session.commit()
    fake_client = FakeImageClient()

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        assert kind == "character_style_reference"
        return f"projects/{project_id}/{kind}/ref.png"

    monkeypatch.setattr("app.tasks.ai.gen_style_reference.get_volcano_client", lambda: fake_client)
    monkeypatch.setattr("app.tasks.ai.gen_style_reference.persist_generated_asset", fake_persist_generated_asset)

    await run_character_style_reference(project.id, job.id, session=db_session)

    await db_session.refresh(project)
    await db_session.refresh(job)
    assert project.character_style_reference_status == "succeeded"
    assert project.character_style_reference_image_url.endswith("/character_style_reference/ref.png")
    assert "角色风格母版" in project.character_style_reference_prompt
    assert job.status == "succeeded"


@pytest.mark.asyncio
async def test_scene_style_reference_task_persists_no_person_prompt(db_session, monkeypatch):
    project = Project(name="雨夜", story="story", ratio="9:16", stage="characters_locked")
    db_session.add(project)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_scene_style_reference", status="queued")
    db_session.add(job)
    await db_session.commit()
    fake_client = FakeImageClient()

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        assert kind == "scene_style_reference"
        return f"projects/{project_id}/{kind}/ref.png"

    monkeypatch.setattr("app.tasks.ai.gen_style_reference.get_volcano_client", lambda: fake_client)
    monkeypatch.setattr("app.tasks.ai.gen_style_reference.persist_generated_asset", fake_persist_generated_asset)

    await run_scene_style_reference(project.id, job.id, session=db_session)

    await db_session.refresh(project)
    assert project.scene_style_reference_status == "succeeded"
    assert "绝对不出现人物" in project.scene_style_reference_prompt
    assert fake_client.calls[0]["size"] == "1344x768"

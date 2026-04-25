import pytest
from importlib import import_module

from app.domain.models import Job, Project, Scene
from app.tasks.ai.gen_scene_asset import run_scene_asset_generation


@pytest.mark.asyncio
async def test_scene_asset_generation_uses_style_reference_and_no_person_prompt(db_session, monkeypatch):
    project = Project(
        name="雨夜",
        story="story",
        ratio="9:16",
        stage="characters_locked",
        scene_style_reference_image_url="projects/p/scene_style_reference/ref.png",
    )
    db_session.add(project)
    await db_session.flush()
    scene = Scene(project_id=project.id, name="朱雀门", theme="palace", summary="雨夜宫门")
    db_session.add(scene)
    await db_session.flush()
    job = Job(project_id=project.id, kind="gen_scene_asset_single", status="queued", target_type="scene", target_id=scene.id)
    db_session.add(job)
    await db_session.commit()
    calls: list[dict] = []

    class FakeClient:
        async def image_generations(self, model, prompt, **kwargs):
            calls.append({"prompt": prompt, **kwargs})
            return {"data": [{"url": "https://volcano.example/tmp-scene.png"}]}

    async def fake_persist_generated_asset(*, url, project_id, kind, ext="png"):
        assert kind == "scene"
        return f"projects/{project_id}/scene/ref.png"

    task_module = import_module("app.tasks.ai.gen_scene_asset")
    monkeypatch.setattr(task_module, "get_volcano_client", lambda: FakeClient())
    monkeypatch.setattr(task_module, "persist_generated_asset", fake_persist_generated_asset)

    await run_scene_asset_generation(scene.id, job.id, session=db_session)

    await db_session.refresh(scene)
    assert scene.reference_image_url.endswith("/scene/ref.png")
    assert calls[0]["size"] == "1344x768"
    assert calls[0]["references"][0].endswith("/scene_style_reference/ref.png")
    assert "绝对不出现人物" in calls[0]["prompt"]


@pytest.mark.asyncio
async def test_scene_asset_generation_marks_parent_failed_when_child_fails(
    db_session,
    monkeypatch,
):
    project = Project(name="雨夜", story="story", ratio="9:16", stage="characters_locked")
    db_session.add(project)
    await db_session.flush()
    scene = Scene(project_id=project.id, name="南门水井", theme="well", summary="雨夜水井")
    db_session.add(scene)
    await db_session.flush()
    parent_job = Job(
        project_id=project.id,
        kind="gen_scene_asset",
        status="running",
        progress=30,
        done=0,
        total=1,
    )
    db_session.add(parent_job)
    await db_session.flush()
    child_job = Job(
        project_id=project.id,
        parent_id=parent_job.id,
        kind="gen_scene_asset_single",
        status="queued",
        target_type="scene",
        target_id=scene.id,
    )
    db_session.add(child_job)
    await db_session.commit()

    class FakeClient:
        async def image_generations(self, model, prompt, **kwargs):
            raise RuntimeError("InputTextSensitiveContentDetected")

    task_module = import_module("app.tasks.ai.gen_scene_asset")
    monkeypatch.setattr(task_module, "get_volcano_client", lambda: FakeClient())

    await run_scene_asset_generation(scene.id, child_job.id, session=db_session)

    await db_session.refresh(parent_job)
    await db_session.refresh(child_job)
    assert child_job.status == "failed"
    assert parent_job.status == "failed"
    assert parent_job.done == 1
    assert parent_job.error_msg is not None
    assert "InputTextSensitiveContentDetected" in parent_job.error_msg

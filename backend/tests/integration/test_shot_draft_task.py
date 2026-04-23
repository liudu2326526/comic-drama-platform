import importlib

import pytest
from sqlalchemy import select

from app.domain.models import Character, Scene
from app.pipeline.states import ProjectStageRaw

from tests.integration.test_shot_render_api import seed_renderable_project


gen_shot_draft_module = importlib.import_module("app.tasks.ai.gen_shot_draft")


@pytest.mark.asyncio
async def test_render_draft_selects_references_before_generating_prompt(
    client, db_session, monkeypatch
):
    project, shot = await seed_renderable_project(db_session)
    project.stage = ProjectStageRaw.CHARACTERS_LOCKED.value
    await db_session.commit()
    scene = (
        await db_session.execute(select(Scene).where(Scene.project_id == project.id))
    ).scalar_one()
    character = (
        await db_session.execute(select(Character).where(Character.project_id == project.id))
    ).scalar_one()

    calls: list[list[dict[str, str]]] = []

    class _Message:
        def __init__(self, content: str):
            self.content = content

    class _Choice:
        def __init__(self, content: str):
            self.message = _Message(content)

    class _Response:
        def __init__(self, content: str):
            self.choices = [_Choice(content)]

    class FakeClient:
        async def chat_completions(self, *args, **kwargs):
            calls.append(kwargs["messages"])
            if len(calls) == 1:
                return _Response(
                    '{"reference_ids":["scene:'
                    + scene.id
                    + '","character:'
                    + character.id
                    + '"],"selection_notes":{"scene":"命中宫殿场景"}}'
                )

            return _Response(
                '{"prompt":"根据选中的场景与人物生成的镜头草稿","optimizer_notes":{"principles":["two-step"]}}'
            )

    monkeypatch.setattr(gen_shot_draft_module, "get_volcano_client", lambda: FakeClient())

    response = await client.post(f"/api/v1/projects/{project.id}/shots/{shot.id}/render-draft")

    assert response.status_code == 200
    job_id = response.json()["data"]["job_id"]
    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_response.status_code == 200
    assert job_response.json()["data"]["status"] == "succeeded"
    assert len(calls) == 2

    draft_response = await client.get(f"/api/v1/projects/{project.id}/shots/{shot.id}/render-draft")
    assert draft_response.status_code == 200
    draft = draft_response.json()["data"]
    assert draft["prompt"] == "根据选中的场景与人物生成的镜头草稿"
    assert [item["id"] for item in draft["references"]] == [
        f"scene:{scene.id}",
        f"character:{character.id}",
    ]

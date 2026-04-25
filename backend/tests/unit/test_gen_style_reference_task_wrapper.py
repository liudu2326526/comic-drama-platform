import pytest
from importlib import import_module

from app.tasks.ai import gen_style_reference

gen_character_asset = import_module("app.tasks.ai.gen_character_asset")
gen_scene_asset = import_module("app.tasks.ai.gen_scene_asset")


@pytest.mark.asyncio
async def test_character_style_reference_task_can_run_inside_existing_event_loop(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def fake_run(project_id: str, job_id: str) -> None:
        calls.append((project_id, job_id))

    monkeypatch.setattr(gen_style_reference, "run_character_style_reference", fake_run)

    gen_style_reference.gen_character_style_reference.run("project-1", "job-1")

    assert calls == [("project-1", "job-1")]


@pytest.mark.asyncio
async def test_character_asset_task_can_run_inside_existing_event_loop(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def fake_run(character_id: str, job_id: str) -> None:
        calls.append((character_id, job_id))

    monkeypatch.setattr(gen_character_asset, "run_character_asset_generation", fake_run)

    gen_character_asset.gen_character_asset.run("character-1", "job-1")

    assert calls == [("character-1", "job-1")]


@pytest.mark.asyncio
async def test_scene_asset_task_can_run_inside_existing_event_loop(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def fake_run(scene_id: str, job_id: str) -> None:
        calls.append((scene_id, job_id))

    monkeypatch.setattr(gen_scene_asset, "run_scene_asset_generation", fake_run)

    gen_scene_asset.gen_scene_asset.run("scene-1", "job-1")

    assert calls == [("scene-1", "job-1")]

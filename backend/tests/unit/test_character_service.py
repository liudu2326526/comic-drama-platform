from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.models import Character, Project
from app.domain.services.character_service import CharacterService


class _SessionStub:
    async def flush(self) -> None:
        return None


class _AssetClientStub:
    def __init__(self) -> None:
        self.closed = False

    async def create_asset_group(self, name: str, description: str | None = None) -> dict:
        return {"Id": "G1"}

    async def create_asset(
        self, group_id: str, url: str, asset_type: str = "Image", name: str = ""
    ) -> dict:
        return {"Id": "A1"}

    async def wait_asset_active(
        self, asset_id: str, *, timeout: int | None = None, interval: int | None = None
    ) -> dict:
        return {"Status": "Active"}

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_register_asset_steps_closes_asset_client(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _AssetClientStub()
    monkeypatch.setattr(
        "app.domain.services.character_service.get_volcano_asset_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "app.domain.services.character_service.build_asset_url",
        lambda url: url,
    )

    character = SimpleNamespace(
        id="CHAR_1",
        project_id="PROJ_1",
        name="Qin Zhao",
        reference_image_url="https://example.com/ref.png",
        video_style_ref=None,
    )

    await CharacterService._register_asset_steps(_SessionStub(), character)

    assert client.closed is True


@pytest.mark.asyncio
async def test_register_asset_steps_persists_active_status(test_engine, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _AssetClientStub()
    monkeypatch.setattr(
        "app.domain.services.character_service.get_volcano_asset_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "app.domain.services.character_service.build_asset_url",
        lambda url: url,
    )

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        project = Project(
            name="Demo",
            story="story",
            stage="storyboard_ready",
            genre="古风",
            ratio="9:16",
        )
        session.add(project)
        await session.flush()

        character = Character(
            project_id=project.id,
            name="萧景珩",
            role_type="supporting",
            summary="",
            description="",
            reference_image_url="https://example.com/ref.png",
            video_style_ref=None,
        )
        session.add(character)
        await session.flush()

        await CharacterService._register_asset_steps(session, character)
        await session.commit()
        await session.refresh(character)

        assert character.video_style_ref["asset_status"] == "Active"
    assert client.closed is True

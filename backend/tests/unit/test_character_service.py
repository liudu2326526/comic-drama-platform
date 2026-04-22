from types import SimpleNamespace

import pytest

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

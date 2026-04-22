from .volcano_client import get_volcano_client
from .volcano_asset_client import VolcanoAssetClient

_asset_client = None

def get_volcano_asset_client() -> VolcanoAssetClient:
    global _asset_client
    if _asset_client is None:
        _asset_client = VolcanoAssetClient()
    return _asset_client

__all__ = ["get_volcano_client", "get_volcano_asset_client"]

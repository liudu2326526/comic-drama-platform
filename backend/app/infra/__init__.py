from .volcano_client import get_volcano_client
from .volcano_asset_client import VolcanoAssetClient

def get_volcano_asset_client() -> VolcanoAssetClient:
    # 不再使用单例, 避免 async 任务中 loop closed 错误
    return VolcanoAssetClient()

__all__ = ["get_volcano_client", "get_volcano_asset_client"]

# 华为云 OBS 集成指南 (Huawei Cloud OBS Integration Guide)

本文档介绍如何在项目中集成华为云 OBS（Object Storage Service）用于文件存储和分发，基于 `app/utils/obs.py` 的实现逻辑。

## 1. 核心依赖

在其他项目中使用前，请确保安装以下依赖：

```bash
pip install esdk-obs-python loguru pydantic-settings
```

- `esdk-obs-python`: 华为云官方 OBS Python SDK。
- `loguru`: 强大的日志记录工具（可选，可替换为标准库 `logging`）。
- `pydantic-settings`: 用于管理环境变量和配置。

## 2. 配置项 (Configuration)

你需要在环境变量或 `.env` 文件中配置以下参数：

| 参数名 | 描述 | 示例 |
| :--- | :--- | :--- |
| `OBS_AK` | 访问密钥 ID (Access Key) | `SFDDLWTCP3BEQUP...` |
| `OBS_SK` | 安全访问密钥 (Secret Key) | `HGqOMwVce3sa0U0f...` |
| `OBS_ENDPOINT` | OBS 服务终端节点 | `obs.cn-south-1.myhuaweicloud.com` |
| `OBS_BUCKET` | 桶名称 | `my-video-bucket` |
| `OBS_PUBLIC_BASE_URL` | 公网访问的基础 URL (CDN 或 自定义域名) | `https://static.example.com` |

## 3. 核心工具类实现 (`obs.py`)

以下是核心逻辑的精简实现，你可以直接复制到你的项目中使用。

### 3.1 初始化 Client

```python
from obs import ObsClient

def get_obs_client(ak, sk, endpoint):
    return ObsClient(
        access_key_id=ak,
        secret_access_key=sk,
        server=endpoint
    )
```

### 3.2 上传本地文件

`upload_file_to_obs` 支持将本地文件上传到指定 Key，并返回可访问的 URL。

```python
def upload_file_to_obs(local_path: str, object_key: str):
    """
    上传本地文件到华为云 OBS
    """
    obs_client = get_obs_client(settings.OBS_AK, settings.OBS_SK, settings.OBS_ENDPOINT)
    try:
        bucket_name = settings.OBS_BUCKET
        resp = obs_client.putFile(bucket_name, object_key, file_path=local_path)
        
        if resp.status < 300:
            base_url = settings.OBS_PUBLIC_BASE_URL.rstrip('/')
            url = f"{base_url}/{object_key}"
            return {"success": True, "object_key": object_key, "url": url}
        else:
            return {"success": False, "error": f"{resp.errorCode}: {resp.errorMessage}"}
    finally:
        obs_client.close()
```

### 3.3 获取访问 URL

```python
def get_obs_url(object_key: str):
    """
    根据 Object Key 拼接完整的公网访问 URL
    """
    base_url = settings.OBS_PUBLIC_BASE_URL.rstrip('/')
    return f"{base_url}/{object_key}"
```

## 4. 进阶用法：集成存储抽象层 (`storage.py`)

为了使项目在本地开发和生产环境之间无缝切换，建议使用统一的存储抽象层。

```python
class BaseStorage(ABC):
    @abstractmethod
    def upload(self, local_path: str, remote_path: str, sync_to_obs: bool = True) -> str: pass
    
    @abstractmethod
    def get_remote_url(self, remote_path: str) -> str: pass

class FileSystemStorage(BaseStorage):
    def upload(self, local_path: str, remote_path: str, sync_to_obs: bool = True) -> str:
        # 1. 先保存到本地
        # ... 保存逻辑 ...
        
        # 2. 如果开启同步，则上传到 OBS
        if sync_to_obs:
            upload_file_to_obs(local_path, remote_path)
        return remote_path
```

## 5. 验证与测试 (CURL)

虽然 OBS 操作通常在后端代码中触发，但你可以通过以下方式验证配置是否正确。

### 5.1 模拟上传 (通过 API 端点)

假设你的后端暴露了一个上传接口 `/api/v1/materials/upload`：

```bash
curl -X 'POST' \
  'http://localhost:6677/api/v1/materials/upload' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@/path/to/your/video.mp4;type=video/mp4'
```

**预期响应**:
```json
{
  "success": true,
  "url": "https://static1203.yingsaidata.com/materials/video_123.mp4",
  "object_key": "materials/video_123.mp4"
}
```

### 5.2 验证 URL 访问
直接在浏览器或使用 `curl -I` 访问返回的 URL：

```bash
curl -I https://static1203.yingsaidata.com/materials/video_123.mp4
```

## 6. 注意事项

1. **权限管理**: 确保 OBS AK/SK 拥有对目标桶的 `PutObject` 和 `GetObject` 权限。
2. **Key 命名**: 建议使用 `path/to/filename.ext` 的格式，OBS 会自动将其识别为文件夹层级。
3. **大文件处理**: 对于超大文件（>100MB），本项目的 `obs.py` 实现了自动视频压缩逻辑，确保 LLM 能够正常处理。
4. **清理**: 任务完成后，记得调用 `delete_object_from_obs` 清理临时存储，节省成本。

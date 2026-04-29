from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"

    # MySQL(组件式)
    mysql_host: str
    mysql_port: int = 3306
    mysql_user: str
    mysql_password: str = ""
    mysql_database: str
    mysql_database_test: str | None = None

    # Redis(组件式)
    redis_host: str
    redis_port: int = 6379
    redis_db: int = 0
    redis_db_broker: int = 1
    redis_db_result: int = 2

    storage_root: str = "/tmp/comic_drama_assets"
    static_base_url: str = "http://127.0.0.1/static/"

    volcano_access_key: str = ""
    volcano_secret_key: str = ""
    ark_api_key: str = ""
    ai_provider_mode: str = "mock"

    # 真实火山配置 (Task 1 新增)
    ark_chat_model: str = "doubao-seed-2-0-pro-260215"
    ark_image_model: str = "doubao-seedream-4-0-250828"
    ark_video_model_standard: str = "doubao-seedance-2-0-260128"
    ark_video_model_fast: str = "doubao-seedance-2-0-fast-260128"
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    # APIMart GPT-Image-2: character style/reference image generation
    apimart_api_key: str = ""
    apimart_base_url: str = "https://api.apimart.ai"
    apimart_image_model: str = "gpt-image-2"
    apimart_image_quality: str = "low"
    apimart_image_output_format: str = "png"
    apimart_poll_interval_sec: float = 5.0
    apimart_poll_timeout_sec: float = 300.0

    # OpenAI-compatible aliases for deployments that already use OPENAI_IMAGE_*
    openai_image_api_key: str = ""
    openai_image_base_url: str = ""
    openai_image_model: str = ""
    ark_video_default_duration: int = 5
    ark_video_default_resolution: str = "720p"
    ark_video_generate_audio: bool = False
    ark_video_watermark: bool = False
    ark_video_return_last_frame: bool = True
    ark_video_execution_expires_after: int = 3600

    # 人像库(AK/SK HMAC)
    volc_access_key_id: str = ""
    volc_secret_access_key: str = ""
    ark_project_name: str = "default"
    volc_asset_host: str = "ark.cn-beijing.volcengineapi.com"
    volc_asset_region: str = "cn-beijing"
    volc_asset_service: str = "ark"
    volc_asset_api_version: str = "2024-01-01"

    # 资产下载
    asset_download_timeout: int = 30       # seconds
    asset_download_chunk: int = 65536

    # 华为云 OBS
    obs_ak: str = ""
    obs_sk: str = ""
    obs_endpoint: str = ""
    obs_bucket: str = ""
    obs_public_base_url: str = ""          # CDN 或自定义域名,必须公网可访问
    obs_mock: bool = False                 # 仅测试/本地 mock 模式允许,real 模式必须 False

    # 轮询
    asset_wait_interval_sec: float = 3.0
    asset_wait_timeout_sec: float = 120.0

    # 调用重试(Chat/Image 粗粒度)
    ai_request_timeout_sec: float = 180.0
    ai_retry_max: int = 3
    ai_retry_base_sec: float = 4.0   # 指数退避 4/16/64

    celery_task_always_eager: bool = False
    backend_cors_origins: str = ""

    ai_worker_concurrency: int = 4
    video_worker_concurrency: int = 2
    ai_rate_limit_per_min: int = 120

    job_progress_history_size: int = 20
    job_progress_estimate_cap: int = 95
    job_progress_estimate_min_seconds: int = 10
    job_progress_default_seconds: int = 120

    def _mysql_url(self, db: str) -> str:
        pwd = quote_plus(self.mysql_password)
        return f"mysql+asyncmy://{self.mysql_user}:{pwd}@{self.mysql_host}:{self.mysql_port}/{db}"

    @property
    def database_url(self) -> str:
        return self._mysql_url(self.mysql_database)

    @property
    def database_url_test(self) -> str | None:
        if not self.mysql_database_test:
            return None
        return self._mysql_url(self.mysql_database_test)

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def celery_broker_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db_broker}"

    @property
    def celery_result_backend(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db_result}"


@lru_cache
def get_settings() -> Settings:
    return Settings()

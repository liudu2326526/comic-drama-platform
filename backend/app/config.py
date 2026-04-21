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

    ai_worker_concurrency: int = 4
    video_worker_concurrency: int = 2
    ai_rate_limit_per_min: int = 120

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

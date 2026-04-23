from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ShotDraftRead(BaseModel):
    id: str
    shot_id: str
    version_no: int
    prompt: str
    references: list[dict[str, Any]]
    optimizer_snapshot: dict[str, Any] | None = None
    created_at: datetime

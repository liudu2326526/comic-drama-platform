from datetime import datetime

from pydantic import BaseModel


class JobDetail(BaseModel):
    id: str
    kind: str
    status: str
    progress: int
    total: int | None
    done: int
    result: dict | None
    error_msg: str | None
    created_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}

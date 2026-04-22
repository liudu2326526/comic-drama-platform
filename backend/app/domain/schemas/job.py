from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class JobSummary(BaseModel):
    id: str
    kind: str
    status: str
    progress: int
    done: int
    total: Optional[int] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

class JobDetail(JobSummary):
    project_id: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    payload: Optional[dict] = None
    result: Optional[dict] = None
    error_msg: Optional[str] = None

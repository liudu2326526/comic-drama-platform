from typing import Literal

from pydantic import BaseModel


StyleReferenceKind = Literal["character", "scene"]
StyleReferenceStatus = Literal["empty", "running", "succeeded", "failed"]


class StyleReferenceState(BaseModel):
    imageUrl: str | None = None
    prompt: str | None = None
    status: StyleReferenceStatus = "empty"
    error: str | None = None


class StyleReferenceJobAck(BaseModel):
    job_id: str


def prompt_text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, dict):
        raw = value.get("prompt")
        return str(raw).strip() if raw else None
    return None

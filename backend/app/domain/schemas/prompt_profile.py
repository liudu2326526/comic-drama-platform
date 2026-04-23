from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PromptProfilePayload(BaseModel):
    prompt: str = Field(min_length=1)
    source: Literal["ai", "manual"]

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt 不能为空")
        return value


class PromptProfileDraftUpdate(BaseModel):
    prompt: str = Field(min_length=1)

    @field_validator("prompt")
    @classmethod
    def strip_and_reject_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt 不能为空白")
        return value


class PromptProfileState(BaseModel):
    draft: PromptProfilePayload | None = None
    applied: PromptProfilePayload | None = None
    status: Literal["empty", "draft_only", "applied", "dirty"] = "empty"


def derive_prompt_profile_state(
    draft: dict | None,
    applied: dict | None,
) -> PromptProfileState:
    if not draft and not applied:
        return PromptProfileState(draft=None, applied=None, status="empty")
    if draft and not applied:
        return PromptProfileState(draft=draft, applied=None, status="draft_only")
    if not draft and applied:
        return PromptProfileState(draft=None, applied=applied, status="applied")
    if draft == applied:
        return PromptProfileState(draft=draft, applied=applied, status="applied")
    return PromptProfileState(draft=draft, applied=applied, status="dirty")

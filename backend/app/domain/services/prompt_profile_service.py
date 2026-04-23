from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Project
from app.domain.schemas.prompt_profile import PromptProfileState, derive_prompt_profile_state


class PromptProfileService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def update_draft(
        self,
        project: Project,
        kind: Literal["character", "scene"],
        prompt: str,
    ) -> PromptProfileState:
        payload = {"prompt": prompt.strip(), "source": "manual"}
        if kind == "character":
            project.character_prompt_profile_draft = payload
            return derive_prompt_profile_state(
                project.character_prompt_profile_draft,
                project.character_prompt_profile_applied,
            )
        project.scene_prompt_profile_draft = payload
        return derive_prompt_profile_state(
            project.scene_prompt_profile_draft,
            project.scene_prompt_profile_applied,
        )

    def clear_draft(
        self,
        project: Project,
        kind: Literal["character", "scene"],
    ) -> PromptProfileState:
        if kind == "character":
            project.character_prompt_profile_draft = None
            return derive_prompt_profile_state(
                project.character_prompt_profile_draft,
                project.character_prompt_profile_applied,
            )
        project.scene_prompt_profile_draft = None
        return derive_prompt_profile_state(
            project.scene_prompt_profile_draft,
            project.scene_prompt_profile_applied,
        )

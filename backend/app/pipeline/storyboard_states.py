from enum import Enum


class StoryboardStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    LOCKED = "locked"


STORYBOARD_ALLOWED_TRANSITIONS: dict[StoryboardStatus, set[StoryboardStatus]] = {
    StoryboardStatus.PENDING: {StoryboardStatus.GENERATING},
    StoryboardStatus.GENERATING: {StoryboardStatus.SUCCEEDED, StoryboardStatus.FAILED},
    StoryboardStatus.SUCCEEDED: {StoryboardStatus.LOCKED, StoryboardStatus.GENERATING},
    StoryboardStatus.FAILED: {StoryboardStatus.GENERATING},
    StoryboardStatus.LOCKED: set(),  # 终态;rollback 另有独立路径
}


def is_storyboard_transition_allowed(
    current: StoryboardStatus, target: StoryboardStatus
) -> bool:
    return target in STORYBOARD_ALLOWED_TRANSITIONS.get(current, set())

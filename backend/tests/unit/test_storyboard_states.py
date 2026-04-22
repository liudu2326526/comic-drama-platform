
from app.pipeline.storyboard_states import (
    STORYBOARD_ALLOWED_TRANSITIONS,
    StoryboardStatus,
    is_storyboard_transition_allowed,
)


def test_pending_to_generating_ok():
    assert is_storyboard_transition_allowed(
        StoryboardStatus.PENDING, StoryboardStatus.GENERATING
    )


def test_generating_to_succeeded_ok():
    assert is_storyboard_transition_allowed(
        StoryboardStatus.GENERATING, StoryboardStatus.SUCCEEDED
    )


def test_generating_to_failed_ok():
    assert is_storyboard_transition_allowed(
        StoryboardStatus.GENERATING, StoryboardStatus.FAILED
    )


def test_failed_to_generating_retry_ok():
    assert is_storyboard_transition_allowed(
        StoryboardStatus.FAILED, StoryboardStatus.GENERATING
    )


def test_succeeded_to_locked_ok():
    assert is_storyboard_transition_allowed(
        StoryboardStatus.SUCCEEDED, StoryboardStatus.LOCKED
    )


def test_pending_to_succeeded_denied():
    # 必须经过 generating
    assert not is_storyboard_transition_allowed(
        StoryboardStatus.PENDING, StoryboardStatus.SUCCEEDED
    )


def test_locked_is_terminal():
    # locked 只能被 rollback 强制重置(不走这条函数);常规跃迁下 locked 是终态
    for tgt in StoryboardStatus:
        if tgt is StoryboardStatus.LOCKED:
            continue
        assert not is_storyboard_transition_allowed(StoryboardStatus.LOCKED, tgt)


def test_transitions_table_has_no_placeholder():
    for src, targets in STORYBOARD_ALLOWED_TRANSITIONS.items():
        assert isinstance(src, StoryboardStatus)
        assert all(isinstance(t, StoryboardStatus) for t in targets)


def test_storyboard_failed_can_transition_to_succeeded_for_version_selection():
    assert is_storyboard_transition_allowed(StoryboardStatus.FAILED, StoryboardStatus.SUCCEEDED) is True

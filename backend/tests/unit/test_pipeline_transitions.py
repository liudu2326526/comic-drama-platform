from app.pipeline.states import ProjectStageRaw, is_forward_allowed, is_rollback_allowed


def test_forward_draft_to_storyboard_ready_ok():
    assert is_forward_allowed(ProjectStageRaw.DRAFT, ProjectStageRaw.STORYBOARD_READY)


def test_forward_skip_stage_denied():
    assert not is_forward_allowed(ProjectStageRaw.DRAFT, ProjectStageRaw.CHARACTERS_LOCKED)


def test_forward_backward_denied():
    assert not is_forward_allowed(ProjectStageRaw.RENDERING, ProjectStageRaw.DRAFT)


def test_rollback_backwards_ok():
    assert is_rollback_allowed(ProjectStageRaw.RENDERING, ProjectStageRaw.STORYBOARD_READY)


def test_rollback_same_stage_denied():
    assert not is_rollback_allowed(ProjectStageRaw.RENDERING, ProjectStageRaw.RENDERING)


def test_rollback_forward_denied():
    assert not is_rollback_allowed(ProjectStageRaw.STORYBOARD_READY, ProjectStageRaw.RENDERING)

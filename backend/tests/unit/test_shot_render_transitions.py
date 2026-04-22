import pytest

from app.pipeline.transitions import (
    InvalidTransition,
    mark_shot_generating,
    mark_shot_locked,
    mark_shot_render_failed,
    mark_shot_render_running,
    mark_shot_render_succeeded,
    select_shot_render_version,
)


class Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_mark_shot_render_running_from_queued():
    render = Obj(status="queued", error_code=None, error_msg=None)
    mark_shot_render_running(render)
    assert render.status == "running"


def test_mark_shot_render_succeeded_updates_render_and_shot():
    shot = Obj(id="shot1", status="generating", current_render_id=None)
    render = Obj(id="render1", status="running", image_url=None, finished_at=None)
    mark_shot_render_succeeded(shot, render, image_url="projects/p/shot/shot1/v1.png")
    assert render.status == "succeeded"
    assert render.image_url == "projects/p/shot/shot1/v1.png"
    assert render.finished_at is not None
    assert shot.status == "succeeded"
    assert shot.current_render_id == "render1"


def test_mark_shot_render_failed_updates_render_and_shot():
    shot = Obj(status="generating")
    render = Obj(status="running", error_code=None, error_msg=None, finished_at=None)
    mark_shot_render_failed(shot, render, error_code="content_filter", error_msg="blocked")
    assert render.status == "failed"
    assert render.error_code == "content_filter"
    assert render.error_msg == "blocked"
    assert render.finished_at is not None
    assert shot.status == "failed"


def test_mark_shot_locked_requires_succeeded_or_locked():
    mark_shot_locked(Obj(status="succeeded"))
    mark_shot_locked(Obj(status="locked"))
    with pytest.raises(InvalidTransition):
        mark_shot_locked(Obj(status="pending"))


def test_select_shot_render_version_requires_succeeded_render():
    shot = Obj(status="failed", current_render_id=None)
    render = Obj(id="render1", status="succeeded")
    select_shot_render_version(shot, render)
    assert shot.status == "succeeded"
    assert shot.current_render_id == "render1"

    with pytest.raises(InvalidTransition):
        select_shot_render_version(Obj(status="failed"), Obj(id="render2", status="failed"))

import pytest
from pydantic import ValidationError

from app.domain.schemas import GenerateJobAck
from app.domain.schemas.project import ProjectCreate, ProjectUpdate
from app.domain.schemas.shot_render import RenderDraftRead, RenderSubmitRequest, RenderVersionRead


class TestProjectCreate:
    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError) as exc:
            ProjectCreate(name="", story="x")
        assert any(e["loc"] == ("name",) for e in exc.value.errors())

    def test_whitespace_name_rejected(self):
        # 纯空白也应当被拒(strip 后为空)
        with pytest.raises(ValidationError):
            ProjectCreate(name="   ", story="x")

    def test_empty_story_rejected(self):
        with pytest.raises(ValidationError):
            ProjectCreate(name="n", story="")

    def test_setup_params_must_be_list(self):
        with pytest.raises(ValidationError):
            ProjectCreate(name="n", story="x", setup_params={"era": "古风"})  # type: ignore[arg-type]

    def test_valid(self):
        p = ProjectCreate(name="测试", story="  故事  ", setup_params=["古风", "冷色调"])
        assert p.name == "测试"
        # story 不 trim,保留用户原文本
        assert p.story == "  故事  "


class TestProjectUpdate:
    def test_empty_payload_ok(self):
        # {} 合法,什么都不改
        p = ProjectUpdate()
        assert p.model_dump(exclude_unset=True) == {}

    def test_explicit_null_name_rejected(self):
        with pytest.raises(ValidationError) as exc:
            ProjectUpdate(name=None)
        assert any("null" in e["msg"].lower() or "none" in e["msg"].lower()
                   for e in exc.value.errors())

    def test_explicit_null_ratio_rejected(self):
        with pytest.raises(ValidationError):
            ProjectUpdate(ratio=None)

    def test_explicit_null_setup_params_rejected(self):
        with pytest.raises(ValidationError):
            ProjectUpdate(setup_params=None)

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            ProjectUpdate(name="")

    def test_partial_ok(self):
        p = ProjectUpdate(name="新名")
        assert p.model_dump(exclude_unset=True) == {"name": "新名"}

    def test_setup_params_list_ok(self):
        p = ProjectUpdate(setup_params=["A", "B"])
        assert p.model_dump(exclude_unset=True) == {"setup_params": ["A", "B"]}

    def test_setup_params_dict_rejected(self):
        with pytest.raises(ValidationError):
            ProjectUpdate(setup_params={"era": "古风"})  # type: ignore[arg-type]


def test_single_render_ack_reuses_generate_job_ack_shape():
    ack = GenerateJobAck(job_id="01HJOB", sub_job_ids=[])
    assert ack.model_dump() == {"job_id": "01HJOB", "sub_job_ids": []}


def test_render_draft_read_supports_prompt_and_references():
    item = RenderDraftRead(
        shot_id="01HSHOT",
        prompt="图片1中的宫门，图片2中的主角，电影感低机位。",
        references=[
            {
                "id": "scene-1",
                "kind": "scene",
                "source_id": "scene01",
                "name": "秦昭入宫",
                "image_url": "https://static.example.com/scene.png",
                "reason": "镜头描述提到宫门",
            }
        ],
    )
    assert item.references[0].kind == "scene"


def test_render_submit_request_accepts_frontend_confirm_payload():
    item = RenderSubmitRequest(
        prompt="图片1中的宫门，图片2中的主角，电影感低机位。",
        references=[
            {
                "id": "scene-1",
                "kind": "scene",
                "source_id": "scene01",
                "name": "秦昭入宫",
                "image_url": "https://static.example.com/scene.png",
            }
        ],
    )
    assert item.references[0].source_id == "scene01"


def test_render_version_read_accepts_prompt_snapshot():
    item = RenderVersionRead(
        id="01HRENDER",
        shot_id="01HSHOT",
        version_no=2,
        status="succeeded",
        prompt_snapshot={"shot": {"title": "镜头 1"}},
        image_url="https://static.example.com/projects/p/shot/s/v2.png",
        error_code=None,
        error_msg=None,
        created_at="2026-04-22T00:00:00",
        finished_at="2026-04-22T00:01:00",
        is_current=True,
    )
    assert item.version_no == 2
    assert item.is_current is True

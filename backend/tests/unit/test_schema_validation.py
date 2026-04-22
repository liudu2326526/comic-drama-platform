import pytest
from pydantic import ValidationError

from app.domain.schemas.project import ProjectCreate, ProjectUpdate


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

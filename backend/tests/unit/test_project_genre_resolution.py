import pytest
from pydantic import ValidationError

from app.domain.schemas.project import ProjectCreate, ProjectUpdate
from app.tasks.ai.parse_novel import normalize_parsed_genre


def test_normalize_parsed_genre_keeps_short_specific_value():
    assert normalize_parsed_genre("现代末世") == "现代末世"


def test_normalize_parsed_genre_rejects_blank_value():
    assert normalize_parsed_genre("   ") is None


def test_project_create_does_not_accept_user_genre():
    with pytest.raises(ValidationError):
        ProjectCreate(name="末世小说", story="现代末世故事", genre="古风权谋")


def test_project_create_has_no_genre_attribute():
    payload = ProjectCreate(name="末世小说", story="现代末世故事")

    assert not hasattr(payload, "genre")


def test_project_update_does_not_accept_user_genre():
    fields = ProjectUpdate.model_fields

    assert "genre" not in fields

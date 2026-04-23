from app.domain.models.job import JOB_KIND_VALUES


def test_job_kind_values_contains_extract_characters():
    assert "extract_characters" in JOB_KIND_VALUES

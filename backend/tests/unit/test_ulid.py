from app.infra.ulid import new_id


def test_new_id_is_26_chars_ulid():
    value = new_id()
    assert isinstance(value, str)
    assert len(value) == 26
    assert value.isalnum()


def test_new_id_monotonically_increases():
    ids = sorted([new_id() for _ in range(100)])
    assert ids == sorted(ids)

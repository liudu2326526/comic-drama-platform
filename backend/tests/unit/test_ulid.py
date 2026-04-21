import time

from app.infra.ulid import new_id


def test_new_id_is_26_chars_ulid():
    value = new_id()
    assert isinstance(value, str)
    assert len(value) == 26
    assert value.isalnum()


def test_new_id_monotonically_increases():
    # 跨不同毫秒生成的 ULID 必然按时间戳前缀升序;
    # 同毫秒内随机段不保证单调,因此用两次取样 + 短 sleep 验证总体单调性
    first = new_id()
    time.sleep(0.002)
    last = new_id()
    assert first < last


def test_new_ids_are_unique():
    ids = {new_id() for _ in range(100)}
    assert len(ids) == 100

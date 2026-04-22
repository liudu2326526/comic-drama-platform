from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: Any = None

    @classmethod
    def success(cls, data: Any = None):
        return cls(code=0, message="ok", data=data)

def ok(data: Any = None) -> dict:
    return {"code": 0, "message": "ok", "data": data}


def fail(code: int, message: str, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}

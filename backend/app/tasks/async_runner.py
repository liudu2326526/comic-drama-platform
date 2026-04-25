import asyncio
import threading
from collections.abc import Coroutine
from typing import Any


def run_async_task(coro: Coroutine[Any, Any, Any]) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return

    error: list[BaseException] = []

    def runner() -> None:
        try:
            asyncio.run(coro)
        except BaseException as exc:  # pragma: no cover
            error.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]


async def dispatch_task_group(task: Any, args_list: list[tuple[Any, ...]]) -> None:
    if not args_list:
        return

    await asyncio.gather(
        *(asyncio.to_thread(task.delay, *args) for args in args_list),
    )

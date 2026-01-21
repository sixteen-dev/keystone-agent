"""Background task utilities for fire-and-forget operations."""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

# Track background tasks to ensure they complete before exit
_background_tasks: set[asyncio.Task] = set()

P = ParamSpec("P")
T = TypeVar("T")


def fire_and_forget(
    func: Callable[P, Coroutine[Any, Any, T]],
) -> Callable[P, asyncio.Task[T] | None]:
    """
    Decorator that runs an async function in the background without blocking.

    The decorated function will:
    - Start immediately as a background task
    - Not block the caller
    - Log any exceptions that occur
    - Be tracked to ensure completion before process exit

    Usage:
        @fire_and_forget
        async def save_to_db(data: dict) -> None:
            await db.insert(data)

        # This returns immediately, save happens in background
        save_to_db({"key": "value"})
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> asyncio.Task[T] | None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, run synchronously (fallback)
            logger.warning(f"No event loop for background task {func.__name__}, running sync")
            asyncio.run(func(*args, **kwargs))
            return None

        task = loop.create_task(func(*args, **kwargs))
        _background_tasks.add(task)

        def _on_done(t: asyncio.Task) -> None:
            _background_tasks.discard(t)
            if t.exception():
                logger.error(f"Background task {func.__name__} failed: {t.exception()}")

        task.add_done_callback(_on_done)
        return task

    return wrapper


async def wait_for_background_tasks(timeout: float = 30.0) -> None:
    """
    Wait for all background tasks to complete.

    Call this before shutting down to ensure all writes complete.

    Args:
        timeout: Maximum seconds to wait
    """
    if not _background_tasks:
        return

    logger.info(f"Waiting for {len(_background_tasks)} background tasks...")

    done, pending = await asyncio.wait(
        _background_tasks,
        timeout=timeout,
        return_when=asyncio.ALL_COMPLETED,
    )

    if pending:
        logger.warning(f"{len(pending)} background tasks did not complete in time")
        for task in pending:
            task.cancel()


def background_tasks_pending() -> int:
    """Return the number of pending background tasks."""
    return len(_background_tasks)


class BackgroundWriter:
    """
    Context manager for batching background writes.

    Ensures all writes complete before exiting the context.

    Usage:
        async with BackgroundWriter() as writer:
            writer.submit(save_to_db(data1))
            writer.submit(save_to_db(data2))
        # All writes guaranteed complete here
    """

    def __init__(self):
        self._tasks: list[asyncio.Task] = []

    def submit(self, coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        """Submit a coroutine to run in the background."""
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task

    async def __aenter__(self) -> "BackgroundWriter":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

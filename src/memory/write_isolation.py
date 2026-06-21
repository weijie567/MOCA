from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

T = TypeVar("T")


async def run_memory_side_effect_in_isolated_session(
    parent_session: AsyncSession,
    operation: Callable[[AsyncSession], Awaitable[T]],
) -> T:
    """Run memory side effects in a child session so rollback cannot affect the caller transaction."""
    session_factory = async_sessionmaker(parent_session.bind, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as memory_session:
        try:
            result = await operation(memory_session)
            await memory_session.commit()
            return result
        except Exception:
            await memory_session.rollback()
            raise

from sqlalchemy.ext.asyncio import AsyncSession


async def seed_defaults(_session: AsyncSession) -> None:
    """Accounts and searches are created per user on register — nothing global."""
    return

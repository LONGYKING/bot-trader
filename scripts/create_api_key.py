"""
Bootstrap script to create the first admin API key.
Run with: make seed-api-key
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from app.db.session import get_session_factory, get_engine
    from app.services.api_key_service import create_api_key

    factory = get_session_factory()
    async with factory() as session:
        api_key, raw_key = await create_api_key(
            session,
            name="admin",
            scopes=["*"],
        )
        await session.commit()
        print(f"\n✓ Admin API key created")
        print(f"  Key ID:     {api_key.id}")
        print(f"  Prefix:     {api_key.key_prefix}...")
        print(f"  Raw key:    {raw_key}")
        print(f"\n  Store this key securely — it will not be shown again.\n")

    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())

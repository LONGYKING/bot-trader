"""
Seed an owner User for the default tenant created by migration 0007.

After running `make migrate`, all pre-existing data is assigned to the default
tenant (00000000-0000-0000-0000-000000000001) but no User row exists, so the
platform owner cannot log in via JWT. This script creates that user.

Usage:
    make seed-owner
    SEED_OWNER_EMAIL=me@example.com SEED_OWNER_PASSWORD=secret make seed-owner
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def main() -> None:
    from app.db.session import get_session_factory, get_engine
    from app.repositories.tenant import UserRepository
    from app.services.auth_service import _hash_password

    email = os.environ.get("SEED_OWNER_EMAIL") or input("Owner email: ").strip()
    password = os.environ.get("SEED_OWNER_PASSWORD") or input("Owner password: ").strip()

    if not email or not password:
        print("Error: email and password are required.")
        sys.exit(1)

    if len(password) < 8:
        print("Error: password must be at least 8 characters.")
        sys.exit(1)

    factory = get_session_factory()
    async with factory() as session:
        repo = UserRepository(session)

        existing = await repo.get_by_email(email)
        if existing:
            print(f"User '{email}' already exists (tenant_id={existing.tenant_id}) — skipping.")
            return

        user = await repo.create(
            {
                "tenant_id": _DEFAULT_TENANT_ID,
                "email": email,
                "password_hash": _hash_password(password),
                "full_name": "Platform Owner",
                "is_owner": True,
            }
        )
        await session.commit()

        print(f"\n✓ Owner user created")
        print(f"  User ID:   {user.id}")
        print(f"  Email:     {user.email}")
        print(f"  Tenant ID: {user.tenant_id}")
        print(f"\n  Log in at /login — this account owns all pre-migration data.\n")

    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())

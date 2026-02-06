"""Seed script for initializing default data.

Creates default roles, modules, and an initial admin user.

Usage:
    python scripts/seed.py
    python scripts/seed.py --admin-password <password>
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.core.config import settings
from api.core.database import Base
from api.core.security import get_password_hash
from api.models.module import DEFAULT_MODULES, Module
from api.models.role import DEFAULT_ROLES, Role
from api.models.user import User


async def seed_roles(session: AsyncSession) -> dict[str, Role]:
    """Create default roles if they don't exist."""
    roles = {}
    for role_data in DEFAULT_ROLES:
        result = await session.execute(select(Role).where(Role.name == role_data["name"]))
        role = result.scalar_one_or_none()

        if role is None:
            role = Role(
                name=role_data["name"],
                description=role_data["description"],
                permissions=role_data["permissions"],
            )
            session.add(role)
            print(f"  Created role: {role_data['name']}")
        else:
            print(f"  Role already exists: {role_data['name']}")

        roles[role_data["name"]] = role

    await session.flush()
    return roles


async def seed_modules(session: AsyncSession) -> None:
    """Create default modules if they don't exist."""
    for module_data in DEFAULT_MODULES:
        result = await session.execute(
            select(Module).where(Module.name == module_data["name"])
        )
        module = result.scalar_one_or_none()

        if module is None:
            module = Module(
                name=module_data["name"],
                display_name=module_data["display_name"],
                description=module_data.get("description", ""),
                category=module_data.get("category", "general"),
                is_core=module_data.get("is_core", False),
                is_enabled=module_data.get("is_enabled", True),
                required_permissions=module_data.get("required_permissions", []),
                config=module_data.get("config", {}),
                default_config=module_data.get("config", {}),
            )
            session.add(module)
            print(f"  Created module: {module_data['name']}")
        else:
            print(f"  Module already exists: {module_data['name']}")

    await session.flush()


async def seed_admin_user(
    session: AsyncSession, roles: dict[str, Role], password: str
) -> None:
    """Create the initial admin user if it doesn't exist."""
    result = await session.execute(select(User).where(User.username == "admin"))
    admin = result.scalar_one_or_none()

    if admin is None:
        admin = User(
            username="admin",
            email="admin@localhost",
            password_hash=get_password_hash(password),
            is_active=True,
            is_superuser=True,
            is_verified=True,
        )
        session.add(admin)
        await session.flush()

        # Assign admin role
        if "admin" in roles:
            admin.roles.append(roles["admin"])

        print(f"  Created admin user (username: admin, password: {password})")
    else:
        print("  Admin user already exists")


async def main(admin_password: str) -> None:
    """Run all seed operations."""
    print(f"Connecting to database: {settings.database_url[:50]}...")

    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        try:
            print("\n[1/3] Seeding roles...")
            roles = await seed_roles(session)

            print("\n[2/3] Seeding modules...")
            await seed_modules(session)

            print("\n[3/3] Seeding admin user...")
            await seed_admin_user(session, roles, admin_password)

            await session.commit()
            print("\nSeed completed successfully!")

        except Exception as e:
            await session.rollback()
            print(f"\nSeed failed: {e}")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the database with default data")
    parser.add_argument(
        "--admin-password",
        default="Admin123!",
        help="Password for the initial admin user (default: Admin123!)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.admin_password))

import asyncio
import os
import sys

# Tambahkan root path ke sys.path agar bisa melakukan import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.user import User
from app.core.security import hash_password

async def create_default_user():
    email = os.getenv("DEFAULT_SUPERADMIN_EMAIL", "admin@admin.com")
    password = os.getenv("DEFAULT_SUPERADMIN_PASSWORD", "admin123")
    name = os.getenv("DEFAULT_SUPERADMIN_NAME", "Super Admin")

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if user:
            print(f"User {email} already exists.")
            return

        new_user = User(
            email=email,
            name=name,
            role="superadmin",
            password_hash=hash_password(password)
        )
        session.add(new_user)
        await session.commit()
        print(f"Successfully created default user: {email} (role: superadmin)")

if __name__ == "__main__":
    asyncio.run(create_default_user())

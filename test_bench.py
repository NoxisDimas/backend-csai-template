import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import engine, async_session_factory as async_session_maker
from app.models.user import User
from app.core.security import hash_password
import httpx
from httpx import ASGITransport
from app.main import app

# Constants for simulation
SUPERADMIN_EMAIL = "superadmin@example.com"
SUPERADMIN_PASS = "supersecret"
SUPERADMIN_NAME = "System Superadmin"

async def setup_default_user():
    """Create default superadmin user directly in the database."""
    print("[*] Setting up default superadmin user...")
    async with async_session_maker() as session:
        # Check if exists
        result = await session.execute(select(User).where(User.email == SUPERADMIN_EMAIL))
        existing = result.scalar_one_or_none()
        if existing:
            print("[*] Superadmin already exists. Skipping creation.")
            return

        superadmin = User(
            name=SUPERADMIN_NAME,
            email=SUPERADMIN_EMAIL,
            role="superadmin",
            password_hash=hash_password(SUPERADMIN_PASS),
        )
        session.add(superadmin)
        await session.commit()
        print("[*] Superadmin created successfully!")
    
    # Dispose of the engine to clear the connection pool tied to this event loop
    # so that TestClient doesn't try to reuse closed connections on a new loop
    await engine.dispose()

async def run_simulation():
    """Run the API simulation using httpx.AsyncClient."""
    print("\n" + "="*50)
    print("🚀 Starting Dashboard Authentication Simulation")
    print("="*50 + "\n")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        # 1. Login as Superadmin
        print(">>> 1. Login as Superadmin")
        res = await client.post("/api/v1/auth/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASS
        })
        
        if res.status_code != 200:
            print(f"❌ Failed to login as superadmin: {res.text}")
            return
            
        token = res.json()["data"]["access_token"]
        print(f"✅ Logged in successfully. Token received.\n")

        # 2. Register new Admin and Staff
        print(">>> 2. Superadmin creating new Admin & Staff")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create Admin
        admin_payload = {
            "name": "New Admin",
            "email": "admin@example.com",
            "password": "adminpassword",
            "role": "admin"
        }
        
        res_admin = await client.post("/api/v1/auth/register", json=admin_payload, headers=headers)
        if res_admin.status_code == 201:
            print("✅ Admin created successfully!")
        elif res_admin.status_code == 409:
            print("⚠️ Admin already exists.")
        else:
            print(f"❌ Failed to create Admin: {res_admin.text}")
            
        # Create Staff
        staff_payload = {
            "name": "New Staff",
            "email": "staff@example.com",
            "password": "staffpassword",
            "role": "staff"
        }
        res_staff = await client.post("/api/v1/auth/register", json=staff_payload, headers=headers)
        if res_staff.status_code == 201:
            print("✅ Staff created successfully!")
        elif res_staff.status_code == 409:
            print("⚠️ Staff already exists.")
        else:
            print(f"❌ Failed to create Staff: {res_staff.text}")
        print()

        # 3. Superadmin logs out (simulate by discarding token)
        print(">>> 3. Superadmin Logs Out (Discard token)")
        headers = {}
        print("✅ Logged out.\n")
        
        # 4. Login as newly created Admin
        print(">>> 4. Login as New Admin")
        res_admin_login = await client.post("/api/v1/auth/login", json={
            "email": admin_payload["email"],
            "password": admin_payload["password"]
        })
        
        if res_admin_login.status_code != 200:
            print(f"❌ Failed to login as Admin: {res_admin_login.text}")
            return
            
        admin_token = res_admin_login.json()["data"]["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print("✅ Admin logged in successfully.\n")
        
        # 5. Admin updates profile (name, email, password)
        print(">>> 5. Admin updates profile (nickname, password)")
        update_payload = {
            "name": "Updated Admin Nickname",
            "password": "newadminpassword"
        }
        res_update = await client.put("/api/v1/auth/me", json=update_payload, headers=admin_headers)
        if res_update.status_code == 200:
            updated_data = res_update.json()["data"]
            print(f"✅ Profile updated successfully! New name: {updated_data['name']}")
        else:
            print(f"❌ Failed to update profile: {res_update.text}")
        print()

        # 6. Admin tries to login with old password (Should fail)
        print(">>> 6. Admin tries login with OLD password")
        res_old = await client.post("/api/v1/auth/login", json={
            "email": admin_payload["email"],
            "password": admin_payload["password"]
        })
        if res_old.status_code != 200:
            print("✅ Login failed as expected with old password.")
        else:
            print("❌ Wait, login succeeded? That's wrong.")
            
        # 7. Admin tries to login with new password (Should succeed)
        print(">>> 7. Admin tries login with NEW password")
        res_new = await client.post("/api/v1/auth/login", json={
            "email": admin_payload["email"],
            "password": "newadminpassword"
        })
        if res_new.status_code == 200:
            print("✅ Login succeeded with new password.")
        else:
            print("❌ Login failed with new password.")
            
        print("\n" + "="*50)
        print("🎉 Simulation Complete!")
        print("="*50 + "\n")

async def main():
    await setup_default_user()
    await run_simulation()

if __name__ == "__main__":
    asyncio.run(main())

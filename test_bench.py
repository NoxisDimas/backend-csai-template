import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import engine, async_session_maker
from app.models.user import User
from app.core.security import hash_password
from fastapi.testclient import TestClient
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

def run_simulation():
    """Run the API simulation using FastAPI TestClient."""
    print("\n" + "="*50)
    print("🚀 Starting Dashboard Authentication Simulation")
    print("="*50 + "\n")

    client = TestClient(app)

    # 1. Login as Superadmin
    print(">>> 1. Login as Superadmin")
    res = client.post("/api/v1/auth/login", json={
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
    
    # Try deleting it first via direct DB or assume it's fresh?
    # TestClient will get 409 if it already exists, let's catch it.
    res_admin = client.post("/api/v1/auth/register", json=admin_payload, headers=headers)
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
    res_staff = client.post("/api/v1/auth/register", json=staff_payload, headers=headers)
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
    res_admin_login = client.post("/api/v1/auth/login", json={
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
    res_update = client.put("/api/v1/auth/me", json=update_payload, headers=admin_headers)
    if res_update.status_code == 200:
        updated_data = res_update.json()["data"]
        print(f"✅ Profile updated successfully! New name: {updated_data['name']}")
    else:
        print(f"❌ Failed to update profile: {res_update.text}")
    print()

    # 6. Admin tries to login with old password (Should fail)
    print(">>> 6. Admin tries login with OLD password")
    res_old = client.post("/api/v1/auth/login", json={
        "email": admin_payload["email"],
        "password": admin_payload["password"]
    })
    if res_old.status_code != 200:
        print("✅ Login failed as expected with old password.")
    else:
        print("❌ Wait, login succeeded? That's wrong.")
        
    # 7. Admin tries to login with new password (Should succeed)
    print(">>> 7. Admin tries login with NEW password")
    res_new = client.post("/api/v1/auth/login", json={
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

if __name__ == "__main__":
    # Ensure event loop runs the async setup first
    asyncio.run(setup_default_user())
    
    # Run the HTTP simulation
    run_simulation()

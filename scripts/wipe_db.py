import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.base_class import Base
from app.db.session import engine
import app.models.product
import app.models.knowledge
import app.models.user
import app.models.config
import app.models.conversation
import app.models.analytics

async def wipe_db():
    async with engine.begin() as conn:
        print("Dropping all tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Recreating all tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("Done!")

if __name__ == "__main__":
    asyncio.run(wipe_db())

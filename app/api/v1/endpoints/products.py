"""
Products endpoints for handling initial Shopify sync and manual syncs.
"""

import hashlib
from typing import Dict, Any
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.dependencies import get_current_admin, get_db
from app.models.product import Product
from app.schemas.common import SuccessResponse, MessageResponse
from app.services.shopify_controller import ShopifyController
from app.core.config import settings
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/products", tags=["Products"])
logger = structlog.get_logger(__name__)


def compute_static_hash(product_data: Dict[str, Any]) -> str:
    """Compute MD5 hash of static product fields."""
    title = product_data.get("title", "")
    desc = product_data.get("description", "")
    ptype = product_data.get("product_type", "")
    tags = product_data.get("tags", "")
    vendor = product_data.get("vendor", "")
    img = product_data.get("image_url", "")
    
    combined = f"{title}|{desc}|{ptype}|{tags}|{vendor}|{img}"
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


@router.post(
    "/sync",
    response_model=SuccessResponse[MessageResponse],
    summary="Sync Products from Shopify",
    description="Fetch all products from Shopify, update local DB, and trigger RAG embedding for new/changed products.",
)
async def sync_products(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    # Require admin authentication (uncomment if you want to protect this endpoint)
    # current_user = Depends(get_current_admin),
) -> SuccessResponse[MessageResponse]:
    """Manually trigger a full product sync."""
    from app.services.config_manager import SystemConfigManager
    from app.core.security import decrypt_data
    from fastapi import HTTPException
    
    sys_config = await SystemConfigManager.get_config(db)
    if not sys_config or not sys_config.shopify_domain or not sys_config.admin_api_token:
        raise HTTPException(status_code=400, detail="Shopify configuration is missing. Please configure it in System Settings.")
        
    controller = ShopifyController(
        domain=sys_config.shopify_domain, 
        token=decrypt_data(sys_config.admin_api_token)
    )
    
    all_products = await controller.get_all_products()
    
    sync_stats = {"new": 0, "updated": 0, "unchanged": 0}
    products_to_embed = []
    
    for p_data in all_products:
        p_id = p_data["id"]
        current_hash = compute_static_hash(p_data)
        
        result = await db.execute(select(Product).where(Product.id == p_id))
        existing_product = result.scalar_one_or_none()
        
        if existing_product:
            if existing_product.static_hash != current_hash:
                # Update existing and re-embed
                existing_product.title = p_data.get("title", "")
                existing_product.handle = p_data.get("handle", "")
                existing_product.description = p_data.get("description", "")
                existing_product.product_type = p_data.get("product_type", "")
                existing_product.tags = p_data.get("tags", "")
                existing_product.vendor = p_data.get("vendor", "")
                existing_product.image_url = p_data.get("image_url")
                existing_product.static_hash = current_hash
                existing_product.embedding_status = "pending"
                
                sync_stats["updated"] += 1
                products_to_embed.append(p_id)
            else:
                sync_stats["unchanged"] += 1
        else:
            # Create new
            new_product = Product(
                id=p_id,
                title=p_data.get("title", ""),
                handle=p_data.get("handle", ""),
                description=p_data.get("description", ""),
                product_type=p_data.get("product_type", ""),
                tags=p_data.get("tags", ""),
                vendor=p_data.get("vendor", ""),
                image_url=p_data.get("image_url"),
                static_hash=current_hash,
                embedding_status="pending"
            )
            db.add(new_product)
            sync_stats["new"] += 1
            products_to_embed.append(p_id)
            
    await db.commit()
    
    # Trigger background embedding tasks
    for pid in products_to_embed:
        background_tasks.add_task(KnowledgeService().process_product_embedding, pid)
        
    msg = f"Sync complete. New: {sync_stats['new']}, Updated: {sync_stats['updated']}, Unchanged: {sync_stats['unchanged']}."
    logger.info("product_sync_completed", stats=sync_stats)
    
    return SuccessResponse(data=MessageResponse(message=msg))

from typing import List
from app.schemas.product_schema import ProductResponse

@router.get(
    "",
    response_model=SuccessResponse[List[ProductResponse]],
    summary="List all Products",
    description="Get a list of all synced products with their embedding status.",
)
async def list_products(
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[List[ProductResponse]]:
    """Get all products."""
    result = await db.execute(select(Product).order_by(Product.created_at.desc()))
    products = result.scalars().all()
    
    return SuccessResponse(
        data=[ProductResponse.model_validate(p) for p in products]
    )

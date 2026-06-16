"""
Shopify Webhook handler endpoint.
Accepts products/create, products/update, products/delete webhooks.
"""

import hmac
import hashlib
import base64
import traceback
import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, Header, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.dependencies import get_db
from app.models.product import Product
from app.models.config import SystemConfig
from app.models.analytics import ErrorLog
from app.core.security import decrypt_data
from app.services.knowledge_service import KnowledgeService
from app.api.v1.endpoints.products import compute_static_hash
from app.services.config_manager import SystemConfigManager
from app.services.telegram_service import fire_telegram_alert, TelegramAlertPayload

router = APIRouter(prefix="/webhook", tags=["Webhook"])
logger = structlog.get_logger(__name__)


async def verify_shopify_webhook(request: Request, db: AsyncSession) -> bool:
    """Verify HMAC signature from Shopify webhook."""
    hmac_header = request.headers.get("x-shopify-hmac-sha256")
    if not hmac_header:
        raise HTTPException(status_code=401, detail="Missing HMAC header")
        
    
    config = await SystemConfigManager.get_config(db)
    
    if not config or not config.webhook_secret:
        logger.warning("webhook_secret_not_configured")
        raise HTTPException(status_code=401, detail="Webhook secret not configured")
        
    secret = decrypt_data(config.webhook_secret).encode("utf-8")
    body = await request.body()
    
    hash_calc = base64.b64encode(
        hmac.new(secret, body, digestmod=hashlib.sha256).digest()
    ).decode("utf-8")
    
    if not hmac.compare_digest(hash_calc, hmac_header):
        logger.warning("webhook_hmac_mismatch", expected=hmac_header, calculated=hash_calc)
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
        
    return True


@router.post("/shopify", status_code=200)
async def shopify_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_shopify_topic: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Shopify webhooks for products.
    Expected topics: products/create, products/update, products/delete
    """
    try:
        await verify_shopify_webhook(request, db)
        
        payload = await request.json()
        logger.info("shopify_webhook_received", topic=x_shopify_topic, product_id=payload.get("id"))
        
        if not x_shopify_topic or not x_shopify_topic.startswith("products/"):
            return {"status": "ignored"}
            
        local_id = payload.get("id")
        if not local_id:
            return {"status": "ignored", "reason": "No ID"}
            
        gid = f"gid://shopify/Product/{local_id}"
        
        if x_shopify_topic in ["products/create", "products/update"]:
            image_src = ""
            image_obj = payload.get("image")
            if image_obj and isinstance(image_obj, dict):
                image_src = image_obj.get("src", "")
                
            current_hash = compute_static_hash({
                "title": payload.get("title", ""),
                "description": payload.get("body_html", ""),
                "product_type": payload.get("product_type", ""),
                "tags": payload.get("tags", ""),
                "vendor": payload.get("vendor", ""),
                "image_url": image_src
            })
            
            result = await db.execute(select(Product).where(Product.id == gid))
            existing_product = result.scalar_one_or_none()
            
            if existing_product:
                if existing_product.static_hash != current_hash:
                    existing_product.title = payload.get("title", "")
                    existing_product.handle = payload.get("handle", "")
                    existing_product.description = payload.get("body_html", "")
                    existing_product.product_type = payload.get("product_type", "")
                    existing_product.tags = payload.get("tags", "")
                    existing_product.vendor = payload.get("vendor", "")
                    existing_product.image_url = image_src
                    existing_product.static_hash = current_hash
                    existing_product.embedding_status = "pending"
                    await db.commit()
                    background_tasks.add_task(KnowledgeService().process_product_embedding, gid)
            else:
                new_product = Product(
                    id=gid,
                    title=payload.get("title", ""),
                    handle=payload.get("handle", ""),
                    description=payload.get("body_html", ""),
                    product_type=payload.get("product_type", ""),
                    tags=payload.get("tags", ""),
                    vendor=payload.get("vendor", ""),
                    image_url=image_src,
                    static_hash=current_hash,
                    embedding_status="pending"
                )
                db.add(new_product)
                await db.commit()
                background_tasks.add_task(KnowledgeService().process_product_embedding, gid)
                
        elif x_shopify_topic == "products/delete":
            result = await db.execute(select(Product).where(Product.id == gid))
            existing_product = result.scalar_one_or_none()
            if existing_product:
                await db.delete(existing_product)
                await db.commit()
                logger.info("product_deleted", product_id=gid)

        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("webhook_processing_error")
        raise e

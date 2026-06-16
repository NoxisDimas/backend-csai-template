"""
Consolidated v1 API router.

Aggregates all v1 endpoint sub-routers into a single router
that gets included at the /api/v1 prefix in the main application.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, config, health, chat, kb, conversations, tickets, inbox, analytics, products, webhook

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(config.router)
api_router.include_router(chat.router)
api_router.include_router(kb.router)
api_router.include_router(conversations.router)
api_router.include_router(tickets.router)
api_router.include_router(inbox.router)
api_router.include_router(analytics.router)
api_router.include_router(products.router)
api_router.include_router(webhook.router)

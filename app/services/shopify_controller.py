"""
Shopify Admin API Controller.

Provides async methods for querying orders, products, and store info
via the Shopify Admin REST API using httpx.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
import structlog
import pybreaker

from app.core.config import get_settings
from app.utils.network_retry import network_retry

logger = structlog.get_logger(__name__)
settings = get_settings()

SHOPIFY_API_VERSION = "2024-01"

# Circuit breaker for Shopify API. Opens after 5 failures, attempts reset after 5 minutes.
shopify_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=300)

class ShopifyController:
    """Async controller for Shopify Admin API interactions."""

    def __init__(self, domain: Optional[str] = None, token: Optional[str] = None) -> None:
        self.domain = domain or None
        self.token = token or None
        self.base_url = (
            f"https://{self.domain}/admin/api/{SHOPIFY_API_VERSION}"
        )
        self.headers = {
            "X-Shopify-Access-Token": self.token,
            "Content-Type": "application/json",
        }

    @shopify_breaker
    @network_retry(max_retries=3, wait_seconds=2.0)
    async def order_lookup(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Look up an order by ID or order number.

        Args:
            order_id: The Shopify order ID or order number (e.g. "#1001").

        Returns:
            A list of order dicts matching the query.
        """
        if self.domain is None or self.token is None:
            logger.error("shopify_order_lookup_failed", error="Domain or token not set")
            raise ValueError("Shopify credentials not configured.")
            
        clean_id = order_id.lstrip("#")
        url = f"{self.base_url}/orders.json"
        params = {"name": order_id, "status": "any", "limit": 5}

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Try by name first
            response = await client.get(
                url, headers=self.headers, params=params
            )
            response.raise_for_status()
            orders = response.json().get("orders", [])

            if not orders and clean_id.isdigit():
                # Fallback: try fetching by numeric ID
                try:
                    single_url = f"{self.base_url}/orders/{clean_id}.json"
                    resp = await client.get(
                        single_url, headers=self.headers
                    )
                    resp.raise_for_status()
                    order = resp.json().get("order")
                    if order:
                        orders = [order]
                except httpx.HTTPStatusError:
                    pass

        logger.info(
            "shopify_order_lookup",
            order_id=order_id,
            results=len(orders),
        )
        return orders

    @shopify_breaker
    @network_retry(max_retries=3, wait_seconds=2.0)
    async def search_products(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for active products by querying via Shopify GraphQL API.

        Args:
            query: The search term (e.g. 't-shirt').
            limit: Max results to return.

        Returns:
            A list of product dicts.
        """
        url = f"{self.base_url}/graphql.json"
        
        # Build GraphQL search query with wildcards for better matching
        search_query = f"title:*{query}* OR *{query}*"
        
        graphql_query = """
        query($searchQuery: String!, $first: Int!) {
          products(first: $first, query: $searchQuery) {
            edges {
              node {
                id
                title
                handle
                description
                onlineStoreUrl
                featuredImage { url }
                variants(first: 3) {
                  edges {
                    node {
                      id
                      title
                      price
                      inventoryQuantity
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "searchQuery": search_query,
            "first": limit
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url, 
                headers=self.headers, 
                json={"query": graphql_query, "variables": variables}
            )
            response.raise_for_status()
            
            data = response.json()
            if "errors" in data:
                logger.error("shopify_graphql_error", errors=data["errors"])
                return []
                
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            
            products = []
            for edge in edges:
                node = edge["node"]
                
                # Format variants to match previous REST structure
                variants = []
                for v_edge in node.get("variants", {}).get("edges", []):
                    v_node = v_edge["node"]
                    # Extract numeric ID from global GraphQL ID
                    v_id = int(v_node["id"].split("/")[-1]) if "id" in v_node else None
                    variants.append({
                        "id": v_id,
                        "title": v_node.get("title"),
                        "price": v_node.get("price"),
                        "inventory_quantity": v_node.get("inventoryQuantity")
                    })
                
                # Extract numeric ID from global GraphQL ID
                p_id = int(node["id"].split("/")[-1]) if "id" in node else None
                image_url = node.get("featuredImage", {}).get("url", "") if node.get("featuredImage") else ""
                store_url = node.get("onlineStoreUrl") or f"https://{self.domain}/products/{node.get('handle')}"
                products.append({
                    "id": p_id,
                    "title": node.get("title"),
                    "handle": node.get("handle"),
                    "description": node.get("description"),
                    "image_url": image_url,
                    "url": store_url,
                    "variants": variants
                })

        logger.info(
            "shopify_search_products_graphql",
            query=query,
            results=len(products),
        )
        return products

    @shopify_breaker
    @network_retry(max_retries=3, wait_seconds=2.0)
    async def get_products_by_ids(self, product_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch specific products by Global IDs to get live dynamic data (price, variants).
        """
        if self.domain is None or self.token is None:
            logger.error("shopify_get_products_by_ids_failed", error="Domain or token not set")
            raise ValueError("Shopify credentials not configured.")

        if not product_ids:
            return []
            
        url = f"{self.base_url}/graphql.json"
        
        # Format the IDs array as a JSON string for GraphQL variable
        graphql_query = """
        query($ids: [ID!]!) {
          nodes(ids: $ids) {
            ... on Product {
              id
              title
              description
              tags
              handle
              onlineStoreUrl
              featuredImage { url }
              variants(first: 10) {
                edges {
                  node {
                    title
                    price
                    inventoryQuantity
                    sku
                  }
                }
              }
            }
          }
        }
        """
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            variables = {"ids": product_ids}
            response = await client.post(
                url, 
                headers=self.headers, 
                json={"query": graphql_query, "variables": variables}
            )
            response.raise_for_status()
            
            data = response.json()
            if "errors" in data:
                logger.error("shopify_graphql_error", errors=data["errors"])
                return []
                
            nodes = data.get("data", {}).get("nodes", [])
            
            products = []
            for node in nodes:
                if not node:
                    continue
                    
                variants = []
                for v_edge in node.get("variants", {}).get("edges", []):
                    v_node = v_edge.get("node", {})
                    variants.append({
                        "title": v_node.get("title"),
                        "price": v_node.get("price"),
                        "inventory_quantity": v_node.get("inventoryQuantity"),
                        "sku": v_node.get("sku")
                    })
                    
                image_url = node.get("featuredImage", {}).get("url", "") if node.get("featuredImage") else ""
                store_url = node.get("onlineStoreUrl") or f"https://{self.domain}/products/{node.get('handle')}"
                
                products.append({
                    "id": node.get("id"),
                    "title": node.get("title"),
                    "description": node.get("description", ""),
                    "tags": node.get("tags", []),
                    "image_url": image_url,
                    "url": store_url,
                    "variants": variants
                })
                
        return products

    @shopify_breaker
    @network_retry(max_retries=3, wait_seconds=2.0)
    async def get_shop_info(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve store metadata (name, email, domain, address, etc.).

        Returns:
            A dict of shop info or None.
        """
        if self.domain is None or self.token is None:
            logger.error("shopify_get_shop_info_failed", error="Domain or token not set")
            raise ValueError("Shopify credentials not configured.")

        url = f"{self.base_url}/shop.json"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            shop = response.json().get("shop")

        logger.info("shopify_get_shop_info", shop_name=shop.get("name") if shop else None)
        return shop

    @shopify_breaker
    @network_retry(max_retries=3, wait_seconds=2.0)
    async def get_all_products(self) -> List[Dict[str, Any]]:
        """
        Fetch all products from Shopify using the REST API.
        Handles pagination internally via Link headers.
        """
        if self.domain is None or self.token is None:
            logger.error("shopify_get_all_products_failed", error="Domain or token not set")
            raise ValueError("Shopify credentials not configured.")
        
        try:
            all_products = []
            url = f"{self.base_url}/products.json"
            params = {"limit": 250}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                while url:
                    response = await client.get(url, headers=self.headers, params=params)
                    response.raise_for_status()
                    
                    # After the first request, we don't need params as they are in the Link URL
                    params = None 
                    
                    data = response.json()
                    products = data.get("products", [])
                    
                    for prod in products:
                        image_obj = prod.get("image")
                        image_url = image_obj.get("src") if image_obj and isinstance(image_obj, dict) else None
                        
                        # Convert tags to a single string for consistency
                        tags_raw = prod.get("tags", "")
                        tags_str = ", ".join(tags_raw) if isinstance(tags_raw, list) else str(tags_raw)
                        
                        all_products.append({
                            "id": f"gid://shopify/Product/{prod.get('id')}",
                            "title": prod.get("title", ""),
                            "handle": prod.get("handle", ""),
                            "description": prod.get("body_html", ""),
                            "product_type": prod.get("product_type", ""),
                            "tags": tags_str,
                            "vendor": prod.get("vendor", ""),
                            "image_url": image_url
                        })
                    
                    # Check for pagination in Link header
                    # Example: <https://shop.myshopify.com/admin/api/2024-01/products.json?page_info=xyz>; rel="next"
                    link_header = response.headers.get("Link")
                    url = None
                    if link_header:
                        links = link_header.split(",")
                        for link in links:
                            if 'rel="next"' in link:
                                # Extract URL from <url>
                                url_part = link.split(";")[0].strip()
                                if url_part.startswith("<") and url_part.endswith(">"):
                                    url = url_part[1:-1]
                                break

            logger.info("shopify_get_all_products", total_fetched=len(all_products))
            return all_products
        except Exception as e:
            from app.services.telegram_service import log_and_alert_error
            logger.error("shopify_get_all_products_failed", error=str(e))
            await log_and_alert_error(e, "ShopifyController", "get_all_products", "Fetching all products")
            raise e
    @shopify_breaker
    @network_retry(max_retries=3, wait_seconds=2.0)
    async def get_store_information(self) -> List[Dict[str, Any]]:
        """
        Fetch all pages and policies from Shopify using the REST API.
        Returns a list of dicts with title, content, and source_id.
        """
        if self.domain is None or self.token is None:
            logger.error("shopify_get_store_information_failed", error="Domain or token not set")
            raise ValueError("Shopify credentials not configured.")
            
        try:
            store_info = []
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1. Fetch Pages
                pages_url = f"{self.base_url}/pages.json"
                pages_params = {"limit": 250}
                
                while pages_url:
                    response = await client.get(pages_url, headers=self.headers, params=pages_params)
                    if response.status_code == 200:
                        pages_params = None
                        data = response.json()
                        pages = data.get("pages", [])
                        
                        for page in pages:
                            content = page.get("body_html")
                            if content and str(content).strip():
                                store_info.append({
                                    "source_id": f"shopify_page_{page.get('id')}",
                                    "title": page.get("title") or "",
                                    "content": content
                                })
                            
                        link_header = response.headers.get("Link")
                        pages_url = None
                        if link_header:
                            for link in link_header.split(","):
                                if 'rel="next"' in link:
                                    url_part = link.split(";")[0].strip()
                                    if url_part.startswith("<") and url_part.endswith(">"):
                                        pages_url = url_part[1:-1]
                                    break
                    else:
                        logger.warning("shopify_pages_fetch_failed", status=response.status_code)
                        break
                        
                # 2. Fetch Policies
                policies_url = f"{self.base_url}/policies.json"
                response = await client.get(policies_url, headers=self.headers)
                if response.status_code == 200:
                    data = response.json()
                    policies = data.get("policies", [])
                    
                    for policy in policies:
                        content = policy.get("body")
                        if content and str(content).strip(): # Only add if policy has content
                            store_info.append({
                                "source_id": f"shopify_policy_{policy.get('title', '').replace(' ', '_').lower()}",
                                "title": policy.get("title") or "",
                                "content": content
                            })
                else:
                    logger.warning("shopify_policies_fetch_failed", status=response.status_code)

            logger.info("shopify_get_store_information", total_fetched=len(store_info))
            return store_info
        except Exception as e:
            from app.services.telegram_service import log_and_alert_error
            logger.error("shopify_get_store_information_failed", error=str(e))
            await log_and_alert_error(e, "ShopifyController", "get_store_information", "Fetching store info pages")
            raise e

    @shopify_breaker
    @network_retry(max_retries=3, wait_seconds=2.0)
    async def get_active_discounts(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Fetch active automatic and code discounts from Shopify via GraphQL.
        """
        if self.domain is None or self.token is None:
            logger.error("shopify_get_active_discounts_failed", error="Domain or token not set")
            raise ValueError("Shopify credentials not configured.")
            
        url = f"{self.base_url}/graphql.json"
        
        graphql_query = """
        query($first: Int!) {
          codeDiscountNodes(first: $first, query: "status:active") {
            nodes {
              codeDiscount {
                ... on DiscountCodeBasic { title summary }
                ... on DiscountCodeBxgy { title summary }
                ... on DiscountCodeFreeShipping { title summary }
              }
            }
          }
          automaticDiscountNodes(first: $first, query: "status:active") {
            nodes {
              automaticDiscount {
                ... on DiscountAutomaticBasic { title summary }
                ... on DiscountAutomaticBxgy { title summary }
                ... on DiscountAutomaticFreeShipping { title summary }
              }
            }
          }
        }
        """
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            variables = {"first": 15}
            logger.info(f"DEBUG get_active_discounts sending GraphQL request to {url}")
            response = await client.post(
                url, 
                headers=self.headers, 
                json={"query": graphql_query, "variables": variables}
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"DEBUG get_active_discounts raw response keys: {list(data.keys())}")
            
            if "errors" in data:
                logger.error("shopify_graphql_error", errors=data["errors"])
                return {"automatic_discounts": [], "code_discounts": []}
                
            code_nodes = data.get("data", {}).get("codeDiscountNodes", {}).get("nodes", [])
            auto_nodes = data.get("data", {}).get("automaticDiscountNodes", {}).get("nodes", [])
            
            result = {
                "automatic_discounts": [],
                "code_discounts": []
            }
            
            for node in auto_nodes:
                discount = node.get("automaticDiscount") or {}
                if discount.get("title"):
                    result["automatic_discounts"].append({
                        "title": discount.get("title"),
                        "summary": discount.get("summary", "Tidak ada detail tambahan")
                    })
                    
            for node in code_nodes:
                discount = node.get("codeDiscount") or {}
                if discount.get("title"):
                    result["code_discounts"].append({
                        "title": discount.get("title"),
                        "summary": discount.get("summary", "Tidak ada detail tambahan")
                    })
                    
            logger.info(f"DEBUG get_active_discounts mapped result: {result}")
            return result

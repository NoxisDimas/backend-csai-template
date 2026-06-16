"""
Shopify Tools for LangGraph agent (factory pattern).

Three tool factories bound to a ShopifyController instance:
  - order_lookup: look up orders by ID/number
  - search_product: search active products
  - get_shop_info: retrieve store metadata
"""

import json
import logging
import pybreaker
from typing import List

from langchain_core.tools import BaseTool, ToolException
from langchain.tools import tool

from app.services.shopify_controller import ShopifyController
from app.services.telegram_service import log_and_alert_error

logger = logging.getLogger(__name__)


def create_order_lookup_tools(
    controller: ShopifyController,
) -> List[BaseTool]:
    """Create order lookup tools bound to the controller."""

    @tool()
    async def order_lookup(order_id: str) -> str:
        """
        Order Lookup

        Searches for orders in the Shopify store by ID or order number.
        Retrieves customer info, items purchased, total amount,
        and order status.

        To use this tool, first request the order ID from the customer.

        Args:
            order_id (str): Unique identifier or order number (e.g. "#1001").

        Returns:
            str: JSON string containing the order details.
        """
        try:
            logger.info(f"Tool order_lookup called: {order_id}")
            orders = await controller.order_lookup(order_id)
            return json.dumps(orders, default=str)
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker OPEN for order_lookup.")
            return "Sistem koneksi ke toko sedang mengalami gangguan sementara. Mohon beritahu pelanggan untuk menunggu beberapa saat lagi."
        except ValueError as e:
            if "not configured" in str(e).lower():
                return "Fitur Shopify belum dikonfigurasi. Beri tahu pelanggan bahwa Anda belum bisa mengakses data pesanan."
            raise e
        except Exception as e:
            logger.exception("Error looking up order in Shopify")
            await log_and_alert_error(e, "Customer Support Agent", "order_lookup tool", f"Looking up order {order_id}")
            raise ToolException("Sistem sedang mengalami kendala saat mencari pesanan. Mohon beri tahu pelanggan.")

    return [order_lookup]


def create_search_product_tools(
    controller: ShopifyController,
) -> List[BaseTool]:
    """Create product search tools bound to the controller."""

    @tool()
    async def search_product(query: str) -> str:
        """
        Search Products (Semantic Vector Search)

        Searches for products in the Shopify store matching the user's query contextually.
        Only active (published and available) products are returned.

        Args:
            query (str): English search term (name, category, material, color).

        Returns:
            str: Formatted string containing a list of matching products and their stock.
        """
        try:
            logger.info(f"Tool search_product called: {query}")
            from app.services.knowledge_service import KnowledgeService
            
            # 1. Vector search in ProductEmbedding via KnowledgeService
            service = KnowledgeService()
            unique_ids = await service.search_products(query, limit=5)
            
            if not unique_ids:
                return "Tidak ada produk yang ditemukan."
            
            # 3. Fetch live data from Shopify
            products = await controller.get_products_by_ids(unique_ids)
            
            if not products:
                return "Tidak ada produk yang ditemukan."
                
            # 4. Format output
            output_lines = []
            for p in products:
                output_lines.append(f"Produk: {p.get('title', 'Unknown Product')}")
                output_lines.append(f"URL: {p.get('url', '')}")
                output_lines.append(f"Image: {p.get('image_url', '')}")
                
                output_lines.append("Varian & Stok:")
                for v in p.get("variants", []):
                    v_title = v.get("title", "Default")
                    stock = v.get("inventory_quantity") or 0
                    v_price = v.get("price", "N/A")
                    status = "Tersedia" if int(stock) > 0 else "Habis"
                    output_lines.append(f"- {v_title}: Harga Rp{v_price}, Stok: {stock} ({status})")
                
                tags = p.get("tags", [])
                if tags:
                    output_lines.append(f"Kategori/Tag: {', '.join(tags)}")
                output_lines.append("") # Blank line separator
                
            return "\n".join(output_lines).strip()
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker OPEN for search_product.")
            return "Sistem koneksi ke toko sedang mengalami gangguan sementara. Mohon beritahu pelanggan untuk menunggu beberapa saat lagi."
        except ValueError as e:
            if "not configured" in str(e).lower():
                return "Fitur Shopify belum dikonfigurasi. Beri tahu pelanggan bahwa Anda belum bisa mengakses data produk."
            raise e
        except Exception as e:
            logger.exception("Error searching products with RAG")
            await log_and_alert_error(e, "Customer Support Agent", "search_product tool", f"Searching product for query: {query}")
            raise ToolException("Sistem sedang mengalami kendala saat mencari produk. Mohon beri tahu pelanggan.")

    return [search_product]


def create_shopify_shop_info_tools(
    controller: ShopifyController,
) -> List[BaseTool]:
    """Create store info retrieval tools bound to the controller."""

    @tool()
    async def get_shop_info() -> str:
        """
        Get Shopify Store Information

        Retrieves the store info including name, email, domain, and address.

        Returns:
            str: JSON string containing the store information.
        """
        try:
            logger.info("Tool get_shop_info called")
            shop = await controller.get_shop_info()
            if shop is None:
                return '{"error": "Shop information not found"}'
            return json.dumps(shop, default=str)
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker OPEN for get_shop_info.")
            return "Sistem koneksi ke toko sedang mengalami gangguan sementara. Mohon beritahu pelanggan untuk menunggu beberapa saat lagi."
        except ValueError as e:
            if "not configured" in str(e).lower():
                return "Fitur Shopify belum dikonfigurasi. Beri tahu pelanggan bahwa Anda belum bisa mengakses data toko."
            raise e
        except Exception as e:
            logger.exception("Error retrieving store information")
            await log_and_alert_error(e, "Customer Support Agent", "get_shop_info tool", "Retrieving store metadata")
            raise ToolException("Sistem sedang mengalami kendala saat mengambil info toko. Mohon beri tahu pelanggan.")

    return [get_shop_info]

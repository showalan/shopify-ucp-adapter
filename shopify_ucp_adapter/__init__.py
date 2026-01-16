"""
Shopify to UCP (Universal Commerce Protocol) Adapter

A protocol adapter that converts Shopify GraphQL/REST API responses 
to Schema.org format for UCP compatibility.
"""

__version__ = "0.1.0"

from .adapter import ShopifyUCPAdapter
from .config import AdapterConfig
from .router import get_ucp_router

__all__ = ["ShopifyUCPAdapter", "AdapterConfig", "get_ucp_router"]

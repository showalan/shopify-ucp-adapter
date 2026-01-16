"""FastAPI router for serving UCP products."""

from typing import Optional
from fastapi import APIRouter, HTTPException

from .adapter import ShopifyUCPAdapter


def get_ucp_router(adapter: ShopifyUCPAdapter) -> APIRouter:
    """
    Create a FastAPI router for UCP endpoints.

    Args:
        adapter: Shopify UCP adapter instance

    Returns:
        APIRouter with async endpoints
    """
    router = APIRouter(prefix="/ucp", tags=["ucp"])

    @router.get("/products/{product_id}")
    async def get_product(product_id: str, flatten_variants: Optional[bool] = False):
        """Get a UCP product by Shopify product ID."""
        if flatten_variants:
            products = await adapter.get_product_as_ucp_variants(product_id)
            return [p.model_dump(mode="json", by_alias=True) for p in products]
        product = await adapter.get_product_as_ucp(product_id)
        return product.model_dump(mode="json", by_alias=True)

    @router.get("/products/by-handle/{handle}")
    async def get_product_by_handle(handle: str, flatten_variants: Optional[bool] = False):
        """Get a UCP product by Shopify handle."""
        product = await adapter.fetch_product_by_handle(handle)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        if flatten_variants:
            products = adapter.transform_product(product)
            return [p.model_dump(mode="json", by_alias=True) for p in products]
        return adapter.convert_to_ucp(product).model_dump(mode="json", by_alias=True)

    return router

"""FastAPI router for serving UCP products."""

from typing import Optional
from decimal import Decimal
from time import perf_counter
from uuid import uuid4
from time import time
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .adapter import ShopifyUCPAdapter
from .storage import BaseStorage, InMemoryStorage
from .circuit_breaker import CircuitBreakerOpen
from .telemetry import get_request_duration_histogram


def get_ucp_router(adapter: ShopifyUCPAdapter, storage: Optional[BaseStorage] = None) -> APIRouter:
    """
    Create a FastAPI router for UCP endpoints.

    Args:
        adapter: Shopify UCP adapter instance

    Returns:
        APIRouter with async endpoints
    """
    router = APIRouter(prefix="/ucp", tags=["ucp"])
    duration_histogram = get_request_duration_histogram()

    logging.basicConfig(filename="commerce.log", level=logging.INFO)
    logger = logging.getLogger("shopify_ucp_adapter")

    class ShippingAddress(BaseModel):
        country_code: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 country code")

    class SessionRequest(BaseModel):
        product_id: str
        variant_id: Optional[str] = None
        quantity: int = Field(1, ge=1)
        shipping_address: Optional[ShippingAddress] = None
        cart_token: Optional[str] = None
        idempotency_key: Optional[str] = None

    session_store: BaseStorage = storage or InMemoryStorage()

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

    @router.post("/sessions")
    async def create_session(request: SessionRequest):
        """Create a UCP session with optional shipping address for tax estimation."""
        start = perf_counter()
        now = time()

        idempotency_key = request.cart_token or request.idempotency_key
        if idempotency_key:
            existing = session_store.get(idempotency_key)
            if existing and now - existing["ts"] <= 300:
                return existing["response"]
        try:
            product = await adapter.fetch_product(request.product_id)
        except CircuitBreakerOpen:
            return {"status": "UCP_STATUS_MAINTENANCE"}
        if not product.variants:
            raise HTTPException(status_code=400, detail="Product has no variants")

        variant = None
        if request.variant_id:
            for v in product.variants:
                if v.id == request.variant_id:
                    variant = v
                    break
            if not variant:
                raise HTTPException(status_code=404, detail="Variant not found")
        else:
            variant = product.variants[0]

        offer = adapter._convert_variant_to_offer(variant, product.online_store_url)
        price = Decimal(offer.price_specification.price)
        subtotal = price * Decimal(request.quantity)

        country = None
        if request.shipping_address and request.shipping_address.country_code:
            country = request.shipping_address.country_code.upper()

        tax_rate = adapter.config.tax.default_rate
        if country and country in adapter.config.tax.region_rates:
            tax_rate = adapter.config.tax.region_rates[country]

        if adapter.config.tax.include_in_price:
            tax_amount = Decimal("0.00")
            total = subtotal
        else:
            tax_amount = (subtotal * Decimal(str(tax_rate))).quantize(Decimal("0.01"))
            total = (subtotal + tax_amount).quantize(Decimal("0.01"))

        duration_ms = (perf_counter() - start) * 1000
        if duration_histogram:
            duration_histogram.record(duration_ms, attributes={"product_id": request.product_id})
        logger.info("session_created", extra={"product_id": request.product_id, "duration_ms": duration_ms})

        session_id = f"sess_{uuid4().hex}"
        response = {
            "session_id": session_id,
            "product_id": request.product_id,
            "variant_id": variant.id,
            "currency": offer.price_specification.price_currency,
            "subtotal": str(subtotal.quantize(Decimal("0.01"))),
            "tax": str(tax_amount),
            "total": str(total),
            "country": country,
        }

        if idempotency_key:
            session_store.set(idempotency_key, {"ts": now, "response": response})

        return response

    return router

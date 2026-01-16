"""Core adapter logic for converting Shopify data to UCP format."""

from typing import List, Optional, Dict, Any, Callable, Union
from decimal import Decimal
from html import unescape
import re
import httpx

from .models.shopify_models import ShopifyProduct, ShopifyVariant
from .models.ucp_models import (
    UCPProduct,
    UCPOffer,
    UCPImage,
    UCPPrice,
    UCPOrganization,
)
from .config import AdapterConfig
from .rate_limiter import TokenBucketRateLimiter, SimpleCache
from .circuit_breaker import CircuitBreaker, CircuitBreakerOpen


class ShopifyUCPAdapter:
    """
    Main adapter class for converting Shopify products to UCP format.
    
    This class handles:
    - Fetching products from Shopify API
    - Rate limiting API calls
    - Caching responses
    - Converting Shopify data to Schema.org/UCP format
    - Handling multi-variant products
    """
    
    def __init__(
        self,
        config: AdapterConfig,
        currency_provider: Optional[Callable[[ShopifyVariant], str]] = None,
        exchange_rate_provider: Optional[Callable[[str, str], Decimal]] = None,
        client: Optional[Any] = None,
    ):
        """
        Initialize the adapter.
        
        Args:
            config: Adapter configuration
            currency_provider: Optional function to override currency per variant
            exchange_rate_provider: Optional function to get FX rates (from_currency, to_currency)
            client: Optional HTTP client (e.g., MockShopifyClient)
        """
        self.config = config
        self.currency_provider = currency_provider
        self.exchange_rate_provider = exchange_rate_provider
        self.circuit_breaker = CircuitBreaker()
        
        # Setup rate limiter
        self.rate_limiter = TokenBucketRateLimiter(
            rate=config.rate_limit.max_requests_per_second,
            burst_size=config.rate_limit.burst_size
        )
        
        # Setup cache
        self.cache = (
            SimpleCache(
                ttl=config.rate_limit.cache_ttl_seconds,
                stale_ttl=config.rate_limit.stale_ttl_seconds
            )
            if config.rate_limit.enable_caching
            else None
        )
        
        # HTTP client
        if client is not None:
            self.client = client
            self._owns_client = False
        else:
            self.client = httpx.AsyncClient(
                base_url=f"https://{config.shopify.shop_domain}",
                headers={
                    "X-Shopify-Access-Token": config.shopify.access_token,
                    "Content-Type": "application/json",
                },
                timeout=30.0
            )
            self._owns_client = True
        
        # Organization for offers
        self.organization = UCPOrganization(
            name=config.organization_name,
            url=config.organization_url
        )
    
    async def close(self):
        """Close HTTP client."""
        if self._owns_client:
            await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _make_request(self, endpoint: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
        """
        Make rate-limited API request to Shopify.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            **kwargs: Additional request parameters
            
        Returns:
            JSON response data
        """
        # Check cache first
        cache_key = f"{method}:{endpoint}"
        if self.cache and method == "GET":
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        
        # Circuit breaker guard
        self.circuit_breaker.guard()

        # Acquire rate limit token
        await self.rate_limiter.acquire()
        
        # Add ETag conditional header if cached
        if self.cache and method == "GET":
            etag = self.cache.get_etag(cache_key)
            if etag:
                headers = kwargs.get("headers", {})
                headers["If-None-Match"] = etag
                kwargs["headers"] = headers

        try:
            # Make request
            response = await self.client.request(method, endpoint, **kwargs)
            if response.status_code == 304 and self.cache and method == "GET":
                cached = self.cache.get(cache_key)
                if cached is not None:
                    return cached
            response.raise_for_status()
            self.circuit_breaker.record_success()
        except (httpx.HTTPStatusError, httpx.RequestError):
            self.circuit_breaker.record_failure()
            if self.cache and method == "GET" and self.config.rate_limit.allow_stale_on_error:
                stale = self.cache.get_stale(cache_key)
                if stale is not None:
                    return stale
            raise
        except CircuitBreakerOpen:
            if self.cache and method == "GET" and self.config.rate_limit.allow_stale_on_error:
                stale = self.cache.get_stale(cache_key)
                if stale is not None:
                    return stale
            raise

        data = response.json()
        
        # Cache GET requests with ETag
        if self.cache and method == "GET":
            self.cache.set(cache_key, data, etag=response.headers.get("ETag"))
        
        return data
    
    async def fetch_product(self, product_id: str) -> ShopifyProduct:
        """
        Fetch a single product from Shopify.
        
        Args:
            product_id: Shopify product ID
            
        Returns:
            Shopify product data
        """
        endpoint = f"/admin/api/{self.config.shopify.api_version}/products/{product_id}.json"
        data = await self._make_request(endpoint)
        return ShopifyProduct(**data["product"])
    
    async def fetch_products(self, limit: int = 50) -> List[ShopifyProduct]:
        """
        Fetch multiple products from Shopify.
        
        Args:
            limit: Maximum number of products to fetch
            
        Returns:
            List of Shopify products
        """
        endpoint = f"/admin/api/{self.config.shopify.api_version}/products.json"
        data = await self._make_request(endpoint, params={"limit": limit})
        return [ShopifyProduct(**p) for p in data["products"]]

    async def fetch_product_by_handle(self, handle: str) -> Optional[ShopifyProduct]:
        """
        Fetch a product by handle.

        Args:
            handle: Shopify product handle

        Returns:
            Shopify product data or None if not found
        """
        endpoint = f"/admin/api/{self.config.shopify.api_version}/products.json"
        data = await self._make_request(endpoint, params={"handle": handle, "limit": 1})
        products = data.get("products", [])
        if not products:
            return None
        return ShopifyProduct(**products[0])
    
    def _calculate_price_with_tax(self, price: str, tax_rate: Optional[float] = None) -> str:
        """
        Calculate price including tax if needed.
        
        Args:
            price: Base price as string
            tax_rate: Tax rate to apply (uses default if None)
            
        Returns:
            Price with tax applied as string
        """
        if tax_rate is None:
            tax_rate = self.config.tax.default_rate
        
        if self.config.tax.include_in_price:
            return price
        
        price_decimal = Decimal(price)
        tax_amount = price_decimal * Decimal(str(tax_rate))
        total = price_decimal + tax_amount
        return str(total.quantize(Decimal("0.01")))

    def _html_to_text(self, value: Optional[str]) -> Optional[str]:
        """Convert HTML content to plain text."""
        if not value:
            return value
        text = re.sub(r"<[^>]+>", " ", value)
        text = re.sub(r"\s+", " ", text)
        return unescape(text).strip()

    def _resolve_currency_and_price(self, variant: ShopifyVariant) -> tuple[str, str]:
        """
        Resolve currency and converted price for a variant.

        If a currency_provider returns a different currency, this will attempt to convert
        using exchange_rate_provider. If conversion fails, it falls back to the original
        currency and price.
        """
        base_currency = variant.price.currency_code or self.config.currency.default_currency
        target_currency = base_currency

        if self.currency_provider:
            try:
                target_currency = self.currency_provider(variant) or base_currency
            except Exception:
                target_currency = base_currency

        if target_currency == base_currency:
            return base_currency, variant.price.amount

        if not self.exchange_rate_provider:
            return target_currency, variant.price.amount

        try:
            rate = self.exchange_rate_provider(base_currency, target_currency)
            converted = (Decimal(variant.price.amount) * rate).quantize(Decimal("0.01"))
            return target_currency, str(converted)
        except Exception:
            return base_currency, variant.price.amount
    
    def _convert_variant_to_offer(
        self, 
        variant: ShopifyVariant, 
        product_url: Optional[str] = None
    ) -> UCPOffer:
        """
        Convert a Shopify variant to a UCP Offer.
        
        Args:
            variant: Shopify product variant
            product_url: Product URL
            
        Returns:
            UCP Offer object
        """
        # Determine currency and base price (possibly converted)
        currency, base_amount = self._resolve_currency_and_price(variant)

        # Calculate final price
        final_price = self._calculate_price_with_tax(base_amount)
        
        # Determine availability
        availability = "InStock" if variant.available else "OutOfStock"
        if variant.inventory:
            if variant.inventory.quantity is not None:
                availability = (
                    "InStock"
                    if variant.inventory.quantity > self.config.inventory.buffer_stock
                    else "OutOfStock"
                )
            else:
                availability = "InStock" if variant.inventory.available else "OutOfStock"
        
        # Create price specification
        price_spec = UCPPrice(
            price=final_price,
            price_currency=currency,
            value_added_tax_included=self.config.tax.include_in_price
        )
        
        # Build variant name from selected options
        variant_name = variant.title if variant.title != "Default Title" else None
        
        return UCPOffer(
            url=product_url,
            price_specification=price_spec,
            item_condition="NewCondition",
            availability=availability,
            seller=self.organization,
            sku=variant.sku,
            gtin=variant.barcode,
            mpn=variant.sku,
            name=variant_name
        )
    
    def convert_to_ucp(self, shopify_product: ShopifyProduct) -> UCPProduct:
        """
        Convert a Shopify product to UCP/Schema.org format.
        
        This method handles multi-variant products by creating a separate
        Offer for each variant, flattening the variant structure.
        
        Args:
            shopify_product: Shopify product to convert
            
        Returns:
            UCP Product in Schema.org format
        """
        # Convert images
        ucp_images = [
            UCPImage(
                url=img.url,
                name=img.alt_text,
                width=img.width,
                height=img.height
            )
            for img in shopify_product.images
        ]
        
        # Convert all variants to offers (flattened)
        offers = [
            self._convert_variant_to_offer(
                variant,
                shopify_product.online_store_url
            )
            for variant in shopify_product.variants
        ]
        
        # Create brand organization
        brand = None
        if shopify_product.vendor:
            brand = UCPOrganization(
                name=shopify_product.vendor
            )
        
        # Create UCP product
        description = (
            self._html_to_text(shopify_product.body_html)
            or self._html_to_text(shopify_product.description_html)
            or shopify_product.description
        )

        keywords = list(dict.fromkeys((shopify_product.tags or []) + ([shopify_product.product_type] if shopify_product.product_type else [])))

        return UCPProduct(
            product_id=shopify_product.id,
            name=shopify_product.title,
            description=description,
            image=ucp_images,
            brand=brand,
            category=shopify_product.product_type,
            keywords=keywords or None,
            offers=offers,
            url=shopify_product.online_store_url,
            date_published=shopify_product.published_at,
            date_modified=shopify_product.updated_at
        )

    def transform_product(self, shopify_raw: Union[ShopifyProduct, Dict[str, Any]]) -> List[UCPProduct]:
        """
        Transform a Shopify product into a list of UCP products, one per variant.

        Args:
            shopify_raw: Shopify product object or raw dict

        Returns:
            List of UCP products (flattened by variant)
        """
        product = shopify_raw if isinstance(shopify_raw, ShopifyProduct) else ShopifyProduct(**shopify_raw)

        ucp_images = [
            UCPImage(
                url=img.url,
                name=img.alt_text,
                width=img.width,
                height=img.height
            )
            for img in product.images
        ]

        brand = None
        if product.vendor:
            brand = UCPOrganization(name=product.vendor)

        description = (
            self._html_to_text(product.body_html)
            or self._html_to_text(product.description_html)
            or product.description
        )

        keywords = list(dict.fromkeys((product.tags or []) + ([product.product_type] if product.product_type else [])))

        results: List[UCPProduct] = []
        for variant in product.variants:
            offer = self._convert_variant_to_offer(variant, product.online_store_url)
            ucp_id = f"shp_{product.id}_{variant.id}"
            variant_suffix = f" - {offer.name}" if offer.name else ""
            results.append(
                UCPProduct(
                    product_id=ucp_id,
                    name=f"{product.title}{variant_suffix}",
                    description=description,
                    image=ucp_images,
                    brand=brand,
                    category=product.product_type,
                    keywords=keywords or None,
                    offers=[offer],
                    url=product.online_store_url,
                    date_published=product.published_at,
                    date_modified=product.updated_at
                )
            )

        return results
    
    async def get_product_as_ucp(self, product_id: str) -> UCPProduct:
        """
        Fetch and convert a product to UCP format in one call.
        
        Args:
            product_id: Shopify product ID
            
        Returns:
            Product in UCP format
        """
        shopify_product = await self.fetch_product(product_id)
        return self.convert_to_ucp(shopify_product)

    async def get_product_as_ucp_variants(self, product_id: str) -> List[UCPProduct]:
        """
        Fetch and convert a product to a list of UCP products (one per variant).

        Args:
            product_id: Shopify product ID

        Returns:
            List of UCP products
        """
        shopify_product = await self.fetch_product(product_id)
        return self.transform_product(shopify_product)
    
    async def get_products_as_ucp(self, limit: int = 50) -> List[UCPProduct]:
        """
        Fetch and convert multiple products to UCP format.
        
        Args:
            limit: Maximum number of products to fetch
            
        Returns:
            List of products in UCP format
        """
        shopify_products = await self.fetch_products(limit)
        return [self.convert_to_ucp(p) for p in shopify_products]
    
    def invalidate_cache(self, product_id: Optional[str] = None):
        """
        Invalidate cache for a specific product or all products.
        
        Args:
            product_id: Specific product ID to invalidate (None for all)
        """
        if not self.cache:
            return
        
        if product_id:
            endpoint = f"/admin/api/{self.config.shopify.api_version}/products/{product_id}.json"
            self.cache.invalidate(f"GET:{endpoint}")
        else:
            self.cache.clear()

    def to_mcp_tool_definition(self, base_url: str) -> dict:
        """
        Return MCP tool definitions for this adapter.

        Args:
            base_url: Base URL of the running UCP server
        """
        return {
            "name": "shopify-ucp",
            "version": "1.0",
            "servers": [
                {
                    "name": "shopify-ucp",
                    "type": "http",
                    "base_url": base_url,
                    "routes": [
                        {
                            "method": "GET",
                            "path": "/ucp/products/{product_id}",
                            "description": "Fetch a product by Shopify product ID. Use this during browsing and discovery.",
                        },
                        {
                            "method": "GET",
                            "path": "/ucp/products/by-handle/{handle}",
                            "description": "Fetch a product by Shopify handle. Use this for direct URL lookups.",
                        },
                        {
                            "method": "POST",
                            "path": "/ucp/sessions",
                            "description": "Create a shopping session. Use this ONLY after the user has confirmed the specific variant (size/color) and is ready to proceed to payment. Do not call this during the browsing phase.",
                        },
                    ],
                }
            ],
        }

"""Core adapter logic for converting Shopify data to UCP format."""

from typing import List, Optional, Dict, Any
from decimal import Decimal
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
    
    def __init__(self, config: AdapterConfig):
        """
        Initialize the adapter.
        
        Args:
            config: Adapter configuration
        """
        self.config = config
        
        # Setup rate limiter
        self.rate_limiter = TokenBucketRateLimiter(
            rate=config.rate_limit.max_requests_per_second,
            burst_size=config.rate_limit.burst_size
        )
        
        # Setup cache
        self.cache = SimpleCache(ttl=config.rate_limit.cache_ttl_seconds) if config.rate_limit.enable_caching else None
        
        # HTTP client
        self.client = httpx.AsyncClient(
            base_url=f"https://{config.shopify.shop_domain}",
            headers={
                "X-Shopify-Access-Token": config.shopify.access_token,
                "Content-Type": "application/json",
            },
            timeout=30.0
        )
        
        # Organization for offers
        self.organization = UCPOrganization(
            name=config.organization_name,
            url=config.organization_url
        )
    
    async def close(self):
        """Close HTTP client."""
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
        
        # Acquire rate limit token
        await self.rate_limiter.acquire()
        
        # Make request
        response = await self.client.request(method, endpoint, **kwargs)
        response.raise_for_status()
        
        data = response.json()
        
        # Cache GET requests
        if self.cache and method == "GET":
            self.cache.set(cache_key, data)
        
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
        # Calculate final price
        final_price = self._calculate_price_with_tax(variant.price.amount)
        
        # Determine availability
        availability = "InStock" if variant.available else "OutOfStock"
        if variant.inventory:
            availability = "InStock" if variant.inventory.available else "OutOfStock"
        
        # Create price specification
        price_spec = UCPPrice(
            price=final_price,
            price_currency=variant.price.currency_code,
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
        return UCPProduct(
            product_id=shopify_product.id,
            name=shopify_product.title,
            description=shopify_product.description,
            image=ucp_images,
            brand=brand,
            category=shopify_product.product_type,
            offers=offers,
            url=shopify_product.online_store_url,
            date_published=shopify_product.published_at,
            date_modified=shopify_product.updated_at
        )
    
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

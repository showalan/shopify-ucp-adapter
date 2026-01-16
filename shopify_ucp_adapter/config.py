"""Configuration management for the Shopify UCP Adapter."""

from typing import Optional, Dict
from pydantic import BaseModel, Field, ConfigDict


class TaxConfig(BaseModel):
    """Tax configuration."""
    default_rate: float = Field(0.0, ge=0.0, le=1.0, description="Default tax rate (0.0 to 1.0)")
    include_in_price: bool = Field(True, description="Whether tax is included in the displayed price")
    region_rates: Dict[str, float] = Field(
        default_factory=dict,
        description="Region-specific tax rates (e.g., {'US': 0.08, 'EU': 0.20})"
    )


class CurrencyConfig(BaseModel):
    """Currency configuration."""
    default_currency: str = Field("USD", description="Default currency code (ISO 4217)")
    supported_currencies: list[str] = Field(
        default_factory=lambda: ["USD"],
        description="List of supported currency codes"
    )


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    max_requests_per_second: float = Field(2.0, gt=0, description="Maximum API requests per second")
    burst_size: int = Field(10, gt=0, description="Maximum burst size for rate limiter")
    enable_caching: bool = Field(True, description="Enable response caching")
    cache_ttl_seconds: int = Field(300, gt=0, description="Cache TTL in seconds")
    allow_stale_on_error: bool = Field(True, description="Return stale cache on API errors")
    stale_ttl_seconds: int = Field(86400, gt=0, description="Max age for stale cache fallback")


class InventoryConfig(BaseModel):
    """Inventory configuration."""
    buffer_stock: int = Field(0, ge=0, description="Buffer stock to prevent overselling")


class ShopifyConfig(BaseModel):
    """Shopify API configuration."""
    shop_domain: str = Field(..., description="Shopify shop domain (e.g., 'mystore.myshopify.com')")
    access_token: str = Field(..., description="Shopify Admin API access token")
    api_version: str = Field("2024-01", description="Shopify API version")
    webhook_secret: Optional[str] = Field(None, description="Webhook verification secret")


class AdapterConfig(BaseModel):
    """Main configuration for Shopify UCP Adapter."""
    shopify: ShopifyConfig
    tax: TaxConfig = Field(default_factory=TaxConfig)
    currency: CurrencyConfig = Field(default_factory=CurrencyConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    inventory: InventoryConfig = Field(default_factory=InventoryConfig)
    
    # Organization info for Schema.org
    organization_name: str = Field(..., description="Your organization name")
    organization_url: Optional[str] = Field(None, description="Your organization website URL")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "shopify": {
                    "shop_domain": "mystore.myshopify.com",
                    "access_token": "shpat_xxxxx",
                    "api_version": "2024-01"
                },
                "organization_name": "My Store",
                "organization_url": "https://mystore.com",
                "tax": {
                    "default_rate": 0.08,
                    "include_in_price": False
                },
                "currency": {
                    "default_currency": "USD"
                },
                "rate_limit": {
                    "max_requests_per_second": 2.0,
                    "burst_size": 10,
                    "enable_caching": True,
                    "cache_ttl_seconds": 300,
                    "allow_stale_on_error": True,
                    "stale_ttl_seconds": 86400
                },
                "inventory": {
                    "buffer_stock": 0
                }
            }
        }
    )

"""Example demonstrating tax calculation with different rates."""

import asyncio
import json
from shopify_ucp_adapter import ShopifyUCPAdapter, AdapterConfig


async def main():
    """Example: Show tax calculation for different regions."""
    
    config = AdapterConfig(
        shopify={
            "shop_domain": "mystore.myshopify.com",
            "access_token": "shpat_xxxxx",
            "api_version": "2024-01"
        },
        organization_name="My Store",
        tax={
            "default_rate": 0.08,  # 8% default
            "include_in_price": False,
            "region_rates": {
                "US": 0.08,
                "CA": 0.13,
                "EU": 0.20
            }
        },
        currency={
            "default_currency": "USD"
        }
    )
    
    async with ShopifyUCPAdapter(config) as adapter:
        # Fetch product
        product = await adapter.get_product_as_ucp("1234567890")
        
        print(f"Product: {product.name}")
        print(f"\nPrices (tax included: {config.tax.include_in_price}):")
        
        for offer in product.offers[:3]:
            price_spec = offer.price_specification
            variant_name = offer.name or "Default"
            print(f"\n  {variant_name}:")
            print(f"    Price: {price_spec.price} {price_spec.price_currency}")
            print(f"    Tax included: {price_spec.value_added_tax_included}")


if __name__ == "__main__":
    asyncio.run(main())

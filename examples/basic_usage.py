"""Example usage of Shopify UCP Adapter."""

import asyncio
import json
from shopify_ucp_adapter import ShopifyUCPAdapter, AdapterConfig


async def main():
    """Example: Fetch products and convert to UCP format."""
    
    # Load configuration
    with open('config.json') as f:
        config_data = json.load(f)
    
    config = AdapterConfig(**config_data)
    
    # Create adapter
    async with ShopifyUCPAdapter(config) as adapter:
        # Fetch single product
        print("Fetching single product...")
        product = await adapter.get_product_as_ucp("1234567890")
        
        # Print as Schema.org JSON-LD
        print("\nProduct in UCP (Schema.org) format:")
        print(json.dumps(
            product.model_dump(mode='json', by_alias=True),
            indent=2,
            default=str
        ))
        
        # Fetch multiple products
        print("\n\nFetching multiple products...")
        products = await adapter.get_products_as_ucp(limit=5)
        print(f"Fetched {len(products)} products")
        
        for p in products:
            print(f"\n- {p.name}")
            print(f"  Variants: {len(p.offers)}")
            for offer in p.offers[:3]:  # Show first 3 offers
                price_spec = offer.price_specification
                print(f"    • {offer.name or 'Default'}: {price_spec.price} {price_spec.price_currency}")


if __name__ == "__main__":
    asyncio.run(main())

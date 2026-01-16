"""Example webhook server implementation."""

from shopify_ucp_adapter import AdapterConfig
from shopify_ucp_adapter.webhook import WebhookHandler, create_webhook_app
import json


# Load configuration
with open('config.json') as f:
    config_data = json.load(f)

config = AdapterConfig(**config_data)

# Create webhook app
app = create_webhook_app(config)

# You can also customize webhook handlers
from shopify_ucp_adapter import ShopifyUCPAdapter

adapter = ShopifyUCPAdapter(config)
handler = WebhookHandler(adapter)

@handler.on('products/update')
async def on_product_update(product_data):
    """Custom handler for product updates."""
    product_id = product_data.get('id')
    print(f"Product {product_id} was updated!")
    
    # Fetch and convert the updated product
    ucp_product = await adapter.get_product_as_ucp(str(product_id))
    print(f"Updated product: {ucp_product.name}")
    
    # Here you could:
    # - Update your database
    # - Notify other services
    # - Update search index
    # etc.

# Run with: uvicorn examples.webhook_server:app --reload

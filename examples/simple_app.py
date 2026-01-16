from fastapi import FastAPI

from shopify_ucp_adapter import AdapterConfig, ShopifyUCPAdapter, get_ucp_router

config = AdapterConfig(
    shopify={
        "shop_domain": "mystore.myshopify.com",
        "access_token": "shpat_xxxxx",
        "api_version": "2024-01",
    },
    organization_name="My Store",
)

app = FastAPI()
adapter = ShopifyUCPAdapter(config)
app.include_router(get_ucp_router(adapter))

# Run: uvicorn examples.simple_app:app --reload
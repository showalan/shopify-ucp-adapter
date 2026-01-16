import pytest
import httpx

from shopify_ucp_adapter.adapter import ShopifyUCPAdapter
from shopify_ucp_adapter.config import AdapterConfig
from shopify_ucp_adapter.models.shopify_models import ShopifyProduct
from shopify_ucp_adapter.router import get_ucp_router
from fastapi import FastAPI
from shopify_ucp_adapter.mock_client import MockShopifyClient


def make_config():
    return AdapterConfig(
        shopify={
            "shop_domain": "mystore.myshopify.com",
            "access_token": "shpat_test",
            "api_version": "2024-01",
        },
        organization_name="My Store",
        currency={"default_currency": "USD"},
        inventory={"buffer_stock": 2},
    )


def sample_product():
    return {
        "id": "gid://shopify/Product/123",
        "title": "T-Shirt",
        "description": "Soft cotton",
        "vendor": "BrandX",
        "productType": "Apparel",
        "handle": "t-shirt",
        "images": [
            {"url": "https://example.com/img1.jpg", "altText": "Front"}
        ],
        "variants": [
            {
                "id": "gid://shopify/ProductVariant/1",
                "title": "Red / Small",
                "sku": "RS",
                "price": {"amount": "29.99", "currencyCode": "EUR"},
                "available": True,
                "inventory": {"available": True, "quantity": 1},
                "selectedOptions": [{"name": "Color", "value": "Red"}],
            },
            {
                "id": "gid://shopify/ProductVariant/2",
                "title": "Blue / Large",
                "sku": "BL",
                "price": {"amount": "39.99", "currencyCode": "EUR"},
                "available": True,
                "inventory": {"available": True, "quantity": 5},
                "selectedOptions": [{"name": "Color", "value": "Blue"}],
            },
        ],
    }


def test_transform_product_flattens_variants():
    adapter = ShopifyUCPAdapter(make_config())
    results = adapter.transform_product(sample_product())
    assert len(results) == 2
    assert results[0].offers[0].name == "Red / Small"
    assert results[1].offers[0].name == "Blue / Large"


def test_buffer_stock_affects_availability():
    adapter = ShopifyUCPAdapter(make_config())
    results = adapter.transform_product(sample_product())
    first_offer = results[0].offers[0]
    second_offer = results[1].offers[0]
    assert first_offer.availability == "OutOfStock"
    assert second_offer.availability == "InStock"


def test_currency_provider_override():
    def currency_provider(_variant):
        return "USD"

    adapter = ShopifyUCPAdapter(make_config(), currency_provider=currency_provider)
    results = adapter.transform_product(sample_product())
    assert results[0].offers[0].price_specification.price_currency == "USD"


def test_exchange_rate_fallback_on_error():
    def currency_provider(_variant):
        return "USD"

    def exchange_rate_provider(_from, _to):
        raise RuntimeError("FX error")

    adapter = ShopifyUCPAdapter(
        make_config(),
        currency_provider=currency_provider,
        exchange_rate_provider=exchange_rate_provider,
    )
    results = adapter.transform_product(sample_product())
    assert results[0].offers[0].price_specification.price_currency == "EUR"


def test_sandbox_mock_client():
    adapter = ShopifyUCPAdapter(make_config(), client=MockShopifyClient())
    results = adapter.transform_product(sample_product())
    assert results


@pytest.mark.asyncio
async def test_router_starts_and_responds():
    config = make_config()
    adapter = ShopifyUCPAdapter(config)
    app = FastAPI()
    app.include_router(get_ucp_router(adapter))

    async def fake_fetch_product(_product_id: str):
        return ShopifyProduct(**sample_product())

    adapter.fetch_product = fake_fetch_product  # type: ignore[assignment]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ucp/products/123")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_session_idempotency():
    config = make_config()
    adapter = ShopifyUCPAdapter(config)
    app = FastAPI()
    app.include_router(get_ucp_router(adapter))

    async def fake_fetch_product(_product_id: str):
        return ShopifyProduct(**sample_product())

    adapter.fetch_product = fake_fetch_product  # type: ignore[assignment]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "product_id": "123",
            "variant_id": "gid://shopify/ProductVariant/1",
            "quantity": 1,
            "cart_token": "cart_abc",
        }
        r1 = await client.post("/ucp/sessions", json=payload)
        r2 = await client.post("/ucp/sessions", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json().get("session_id") == r2.json().get("session_id")

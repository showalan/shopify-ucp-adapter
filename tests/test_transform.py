import pytest

from shopify_ucp_adapter.adapter import ShopifyUCPAdapter
from shopify_ucp_adapter.config import AdapterConfig


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

"""Mock Shopify client for sandbox mode."""

from typing import Any, Dict, Optional


class MockResponse:
    """Minimal response object compatible with adapter usage."""

    def __init__(self, data: Dict[str, Any], status_code: int = 200, headers: Optional[Dict[str, str]] = None):
        self._data = data
        self.status_code = status_code
        self.headers = headers or {}

    def json(self) -> Dict[str, Any]:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"Mock HTTP error {self.status_code}")


class MockShopifyClient:
    """Mock Shopify client that returns sample data."""

    def __init__(self):
        self._product = {
            "product": {
                "id": "gid://shopify/Product/123",
                "title": "Mock T-Shirt",
                "body_html": "<p>Soft cotton t-shirt</p>",
                "vendor": "MockBrand",
                "productType": "Apparel",
                "handle": "mock-t-shirt",
                "images": [
                    {"url": "https://example.com/img1.jpg", "altText": "Front"}
                ],
                "variants": [
                    {
                        "id": "gid://shopify/ProductVariant/1",
                        "title": "Red / Small",
                        "sku": "RS",
                        "price": {"amount": "29.99", "currencyCode": "USD"},
                        "available": True,
                        "inventory": {"available": True, "quantity": 10},
                    }
                ],
            }
        }

    async def request(self, _method: str, _endpoint: str, **_kwargs) -> MockResponse:
        return MockResponse(self._product)

    async def aclose(self) -> None:
        return None

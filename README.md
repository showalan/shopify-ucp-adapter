# Shopify UCP Adapter

> **Protocol Adapter**: Convert Shopify GraphQL/REST responses into Google UCP (Schema.org) format.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 Overview

This Python package converts Shopify product data into UCP (Universal Commerce Protocol) Schema.org format. It provides:

- ✅ Shopify private API → Schema.org conversion
- ✅ Flattened multi-variant offers
- ✅ Built-in rate limiting to avoid Shopify API throttling
- ✅ Webhook listener for real-time updates
- ✅ Configurable tax calculation and default currency
- ✅ Response caching with TTL

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/shopify-ucp-adapter.git
cd shopify-ucp-adapter

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or install in editable mode
pip install -e .
```

### Initialize Configuration

```bash
# Generate a config template
shopify-ucp init

# Edit config.json with your Shopify credentials
```

Config example:

```json
{
  "shopify": {
    "shop_domain": "your-store.myshopify.com",
    "access_token": "shpat_your_access_token_here",
    "api_version": "2024-01",
    "webhook_secret": "your_webhook_secret"
  },
  "organization_name": "Your Store Name",
  "organization_url": "https://yourstore.com",
  "tax": {
    "default_rate": 0.08,
    "include_in_price": false,
    "region_rates": {
      "US": 0.08,
      "EU": 0.20
    }
  },
  "currency": {
    "default_currency": "USD",
    "supported_currencies": ["USD", "EUR", "GBP"]
  },
  "rate_limit": {
    "max_requests_per_second": 2.0,
    "burst_size": 10,
    "enable_caching": true,
    "cache_ttl_seconds": 300,
    "allow_stale_on_error": true,
    "stale_ttl_seconds": 86400
  },
  "inventory": {
    "buffer_stock": 0
  }
}
```

## 📖 Usage

### Command Line

```bash
# Fetch a single product and convert to UCP
shopify-ucp fetch 1234567890

# Fetch multiple products
shopify-ucp fetch --limit 20 --output products.json

# Fetch by Shopify product URL
shopify-ucp from-url "https://your-store.myshopify.com/products/red-shirt" --flatten-variants

# Validate configuration
shopify-ucp validate

# Start webhook server
shopify-ucp serve --host 0.0.0.0 --port 8000
```

### Python API

#### Basic Usage

```python
import asyncio
import json
from shopify_ucp_adapter import ShopifyUCPAdapter, AdapterConfig

async def main():
    # Load config
    with open('config.json') as f:
        config_data = json.load(f)
    
    config = AdapterConfig(**config_data)
    
    # Create adapter
    async with ShopifyUCPAdapter(config) as adapter:
        # Fetch single product
        product = await adapter.get_product_as_ucp("1234567890")
        
        # Output Schema.org JSON-LD
        print(json.dumps(
            product.model_dump(mode='json', by_alias=True),
            indent=2,
            default=str
        ))
        
        # Fetch multiple products
        products = await adapter.get_products_as_ucp(limit=10)
        print(f"Fetched {len(products)} products")

asyncio.run(main())
```

#### Currency Provider

You can override the currency per variant (e.g., based on request locale):

```python
def currency_provider(variant):
  return "USD"

async with ShopifyUCPAdapter(config, currency_provider=currency_provider) as adapter:
  product = await adapter.get_product_as_ucp("1234567890")
```

#### Webhook Listener

```python
from shopify_ucp_adapter import AdapterConfig
from shopify_ucp_adapter.webhook import create_webhook_app

config = AdapterConfig(**config_data)
app = create_webhook_app(config)

# Run with:
# uvicorn your_module:app --host 0.0.0.0 --port 8000
```

Custom webhook handler:

```python
from shopify_ucp_adapter import ShopifyUCPAdapter
from shopify_ucp_adapter.webhook import WebhookHandler

adapter = ShopifyUCPAdapter(config)
handler = WebhookHandler(adapter)

@handler.on('products/update')
async def on_product_update(product_data):
    """Triggered when a product is updated."""
    product_id = product_data.get('id')
    print(f"Product {product_id} updated")
    
    ucp_product = await adapter.get_product_as_ucp(str(product_id))
    
    # You can:
    # - update your database
    # - notify other services
    # - update search index
    # etc.

app = handler.create_fastapi_app()
```

## 🏗️ Project Structure

```
shopify-ucp-adapter/
├── shopify_ucp_adapter/
│   ├── __init__.py          # Package entry
│   ├── adapter.py           # Core adapter logic
│   ├── config.py            # Configuration
│   ├── rate_limiter.py      # Rate limiter
│   ├── webhook.py           # Webhook handler
│   ├── cli.py               # CLI
│   ├── router.py            # FastAPI router
│   └── models/
│       ├── shopify_models.py  # Shopify models
│       └── ucp_models.py      # UCP/Schema.org models
├── examples/                # Examples
├── tests/                   # Tests
├── requirements.txt         # Dependencies
├── pyproject.toml           # Project config
└── README.md                # This file
```

## 🔑 Core Features

### 1. Rate Limiting

Uses a **Token Bucket** algorithm to prevent API throttling:

```python
async with ShopifyUCPAdapter(config) as adapter:
    for i in range(100):
        product = await adapter.get_product_as_ucp(str(i))
```

Config parameters:
- `max_requests_per_second`: max requests per second (default 2.0)
- `burst_size`: allowed burst requests (default 10)

### 2. Caching

TTL cache to reduce repeated calls:

```python
config.rate_limit.enable_caching = True
config.rate_limit.cache_ttl_seconds = 300
config.rate_limit.allow_stale_on_error = True
config.rate_limit.stale_ttl_seconds = 86400

adapter.invalidate_cache()  # clear all
adapter.invalidate_cache("1234567890")  # clear specific product
```

### 3. Variant Flattening

Each Shopify variant becomes a UCP `Offer`:

**Shopify format**:
```json
{
  "product": {
    "id": "123",
    "title": "T-Shirt",
    "variants": [
      {"title": "Red/Small", "price": "29.99"},
      {"title": "Red/Medium", "price": "29.99"},
      {"title": "Blue/Large", "price": "29.99"}
    ]
  }
}
```

**UCP format**:
```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "T-Shirt",
  "offers": [
    {
      "@type": "Offer",
      "name": "Red/Small",
      "priceSpecification": {"price": "29.99", "priceCurrency": "USD"}
    },
    {
      "@type": "Offer",
      "name": "Red/Medium",
      "priceSpecification": {"price": "29.99", "priceCurrency": "USD"}
    },
    {
      "@type": "Offer",
      "name": "Blue/Large",
      "priceSpecification": {"price": "29.99", "priceCurrency": "USD"}
    }
  ]
}
```

### 4. Tax Calculation

Flexible tax rules:

```python
config.tax.default_rate = 0.08
config.tax.include_in_price = False
config.tax.region_rates = {
    "US": 0.08,
    "CA": 0.13,
    "EU": 0.20
}
```

### 5. Inventory Buffer

Prevent overselling by declaring OutOfStock when inventory is low:

```python
config.inventory.buffer_stock = 2
```

### 6. Webhook Updates

Receive real-time updates and invalidate cache:

```bash
shopify-ucp serve --port 8000

# Webhook endpoint: http://your-domain.com:8000/webhooks/shopify
```

In Shopify Admin:
1. Settings → Notifications
2. Create webhook
3. Events: `Product creation`, `Product update`, `Product deletion`
4. URL: `http://your-domain.com:8000/webhooks/shopify`

## 🔌 FastAPI Router (Async)

Use `get_ucp_router` to expose async endpoints:

```python
from fastapi import FastAPI
from shopify_ucp_adapter import ShopifyUCPAdapter, AdapterConfig, get_ucp_router

app = FastAPI()
adapter = ShopifyUCPAdapter(config)
app.include_router(get_ucp_router(adapter))
```

Endpoints:
- `GET /ucp/products/{product_id}`
- `GET /ucp/products/by-handle/{handle}`

Add `?flatten_variants=true` to return one UCP product per variant.

## 🤖 Using with mcp-bridge-server

Example: expose the router behind an MCP bridge:

```python
from fastapi import FastAPI
from shopify_ucp_adapter import ShopifyUCPAdapter, AdapterConfig, get_ucp_router

app = FastAPI()
adapter = ShopifyUCPAdapter(config)
app.include_router(get_ucp_router(adapter))

# Then register this FastAPI app in your mcp-bridge-server configuration.
```

## 🧪 Testing

```bash
pytest
pytest --cov=shopify_ucp_adapter --cov-report=html
```

## 📝 Development

### Local Development Setup

```bash
git clone https://github.com/yourusername/shopify-ucp-adapter.git
cd shopify-ucp-adapter

pip install -e ".[dev]"

black shopify_ucp_adapter/
ruff check shopify_ucp_adapter/
mypy shopify_ucp_adapter/
```

### Contributing

1. Fork the project
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to your branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🔒 Security Notes

- ⚠️ Never commit `config.json` or any secrets to version control
- 🔐 Use environment variables for sensitive values
- 🛡️ Use HTTPS and webhook signature verification in production

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

## 🤝 Support

- 📫 Issues: [GitHub Issues](https://github.com/yourusername/shopify-ucp-adapter/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/shopify-ucp-adapter/discussions)
- 📖 Docs: [Documentation](https://github.com/yourusername/shopify-ucp-adapter#readme)

## 🙏 Acknowledgements

- [Shopify API](https://shopify.dev/api)
- [Schema.org](https://schema.org/)
- [Pydantic](https://pydantic.dev/)
- [FastAPI](https://fastapi.tiangolo.com/)

---

Made with ❤️ for the e-commerce community

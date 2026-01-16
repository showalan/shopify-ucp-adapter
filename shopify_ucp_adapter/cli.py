"""Command-line interface for Shopify UCP Adapter."""

import asyncio
import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import typer
from rich.console import Console
from rich.table import Table
from rich.json import JSON

from .adapter import ShopifyUCPAdapter
from .config import AdapterConfig

app = typer.Typer(
    name="shopify-ucp",
    help="Shopify to UCP Protocol Adapter CLI"
)
console = Console()


def load_config(config_path: str) -> AdapterConfig:
    """Load configuration from JSON file."""
    config_file = Path(config_path)
    if not config_file.exists():
        console.print(f"[red]Error: Config file not found: {config_path}[/red]")
        raise typer.Exit(1)
    
    with open(config_file) as f:
        config_data = json.load(f)
    
    return AdapterConfig(**config_data)


def extract_handle_from_url(product_url: str) -> Optional[str]:
    """Extract Shopify product handle from a product URL."""
    parsed = urlparse(product_url)
    if not parsed.path:
        return None
    parts = [p for p in parsed.path.split('/') if p]
    if len(parts) >= 2 and parts[-2] == "products":
        return parts[-1]
    return None


@app.command()
def init(
    output: str = typer.Option("config.json", help="Output configuration file path")
):
    """Initialize a new configuration file with example values."""
    example_config = {
        "shopify": {
            "shop_domain": "your-store.myshopify.com",
            "access_token": "shpat_your_access_token_here",
            "api_version": "2024-01",
            "webhook_secret": "your_webhook_secret_here"
        },
        "organization_name": "Your Store Name",
        "organization_url": "https://yourstore.com",
        "tax": {
            "default_rate": 0.08,
            "include_in_price": False,
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
            "enable_caching": True,
            "cache_ttl_seconds": 300,
            "allow_stale_on_error": True,
            "stale_ttl_seconds": 86400
        },
        "inventory": {
            "buffer_stock": 0
        }
    }
    
    output_path = Path(output)
    with open(output_path, 'w') as f:
        json.dump(example_config, f, indent=2)
    
    console.print(f"[green]✓[/green] Configuration file created: {output}")
    console.print("\n[yellow]⚠ Please edit the file and add your Shopify credentials![/yellow]")


@app.command()
def fetch(
    product_id: Optional[str] = typer.Argument(None, help="Specific product ID to fetch"),
    config: str = typer.Option("config.json", help="Configuration file path"),
    limit: int = typer.Option(10, help="Number of products to fetch (if no product_id)"),
    output: Optional[str] = typer.Option(None, help="Output file for JSON (optional)"),
):
    """Fetch product(s) from Shopify and convert to UCP format."""
    
    async def _fetch():
        cfg = load_config(config)
        
        async with ShopifyUCPAdapter(cfg) as adapter:
            if product_id:
                console.print(f"[blue]Fetching product {product_id}...[/blue]")
                ucp_product = await adapter.get_product_as_ucp(product_id)
                products = [ucp_product]
            else:
                console.print(f"[blue]Fetching {limit} products...[/blue]")
                products = await adapter.get_products_as_ucp(limit)
            
            # Display results
            table = Table(title="Converted Products")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Offers", justify="right", style="yellow")
            table.add_column("Images", justify="right", style="magenta")
            
            for product in products:
                table.add_row(
                    product.product_id,
                    product.name[:50] + "..." if len(product.name) > 50 else product.name,
                    str(len(product.offers)),
                    str(len(product.image))
                )
            
            console.print(table)
            
            # Output to file if requested
            if output:
                output_path = Path(output)
                with open(output_path, 'w') as f:
                    json.dump(
                        [p.model_dump(mode='json', by_alias=True) for p in products],
                        f,
                        indent=2,
                        default=str
                    )
                console.print(f"\n[green]✓[/green] Saved to {output}")
            else:
                # Print first product as example
                if products:
                    console.print("\n[bold]Example UCP Product:[/bold]")
                    console.print(JSON(
                        json.dumps(
                            products[0].model_dump(mode='json', by_alias=True),
                            default=str,
                            indent=2
                        )
                    ))
    
    asyncio.run(_fetch())


@app.command()
def serve(
    config: str = typer.Option("config.json", help="Configuration file path"),
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
):
    """Start webhook server to receive Shopify events."""
    from .webhook import create_webhook_app
    import uvicorn
    
    cfg = load_config(config)
    webhook_app = create_webhook_app(cfg)
    
    console.print(f"[green]Starting webhook server on {host}:{port}[/green]")
    console.print(f"[blue]Webhook endpoint: http://{host}:{port}/webhooks/shopify[/blue]")
    
    uvicorn.run(webhook_app, host=host, port=port)


@app.command()
def validate(
    config: str = typer.Option("config.json", help="Configuration file path"),
):
    """Validate configuration file."""
    try:
        cfg = load_config(config)
        console.print("[green]✓[/green] Configuration is valid!")
        console.print(f"\n[bold]Shop:[/bold] {cfg.shopify.shop_domain}")
        console.print(f"[bold]Organization:[/bold] {cfg.organization_name}")
        console.print(f"[bold]Default Currency:[/bold] {cfg.currency.default_currency}")
        console.print(f"[bold]Tax Rate:[/bold] {cfg.tax.default_rate * 100}%")
    except Exception as e:
        console.print(f"[red]✗ Configuration error:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command("export-mcp")
def export_mcp(
    output: str = typer.Option("mcp.json", help="Output MCP config file path"),
    base_url: str = typer.Option("http://localhost:8000", help="Base URL of your UCP server"),
):
    """Generate an MCP config file for Claude Desktop or Cursor."""
    mcp_config = {
        "name": "shopify-ucp",
        "version": "1.0",
        "servers": [
            {
                "name": "shopify-ucp",
                "type": "http",
                "base_url": base_url,
                "routes": [
                    {"method": "GET", "path": "/ucp/products/{product_id}"},
                    {"method": "GET", "path": "/ucp/products/by-handle/{handle}"},
                    {"method": "POST", "path": "/ucp/sessions"},
                ],
            }
        ],
    }

    output_path = Path(output)
    with open(output_path, "w") as f:
        json.dump(mcp_config, f, indent=2)

    console.print(f"[green]✓[/green] MCP config created: {output}")


@app.command("from-url")
def from_url(
    product_url: str = typer.Argument(..., help="Shopify product URL"),
    config: str = typer.Option("config.json", help="Configuration file path"),
    flatten_variants: bool = typer.Option(False, help="Return one UCP product per variant"),
):
    """Fetch a product by URL and print the converted UCP JSON."""

    async def _from_url():
        cfg = load_config(config)
        handle = extract_handle_from_url(product_url)
        if not handle:
            console.print("[red]Error: Could not extract product handle from URL.[/red]")
            raise typer.Exit(1)

        async with ShopifyUCPAdapter(cfg) as adapter:
            product = await adapter.fetch_product_by_handle(handle)
            if not product:
                console.print("[red]Error: Product not found for the given URL.[/red]")
                raise typer.Exit(1)

            if flatten_variants:
                products = adapter.transform_product(product)
                console.print(JSON(
                    json.dumps(
                        [p.model_dump(mode='json', by_alias=True) for p in products],
                        default=str,
                        indent=2
                    )
                ))
                return

            ucp_product = adapter.convert_to_ucp(product)
            console.print(JSON(
                json.dumps(
                    ucp_product.model_dump(mode='json', by_alias=True),
                    default=str,
                    indent=2
                )
            ))

    asyncio.run(_from_url())


if __name__ == "__main__":
    app()

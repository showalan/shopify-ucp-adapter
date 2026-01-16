"""Webhook handler for Shopify events."""

import hmac
import hashlib
from typing import Callable, Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, status
import json

from .adapter import ShopifyUCPAdapter
from .config import AdapterConfig


class WebhookHandler:
    """
    Handle Shopify webhooks for real-time product updates.
    
    Supports webhook topics:
    - products/create
    - products/update
    - products/delete
    """
    
    def __init__(self, adapter: ShopifyUCPAdapter, webhook_secret: Optional[str] = None):
        """
        Initialize webhook handler.
        
        Args:
            adapter: Shopify UCP adapter instance
            webhook_secret: Secret for webhook verification
        """
        self.adapter = adapter
        self.webhook_secret = webhook_secret or adapter.config.shopify.webhook_secret
        self._handlers: Dict[str, list] = {}
    
    def verify_webhook(self, data: bytes, hmac_header: str) -> bool:
        """
        Verify Shopify webhook signature.
        
        Args:
            data: Raw request body
            hmac_header: HMAC header from Shopify
            
        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            return True  # Skip verification if no secret configured
        
        computed_hmac = hmac.new(
            self.webhook_secret.encode('utf-8'),
            data,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_hmac, hmac_header)
    
    def on(self, topic: str):
        """
        Decorator to register webhook event handlers.
        
        Args:
            topic: Webhook topic (e.g., 'products/update')
            
        Example:
            @webhook_handler.on('products/update')
            async def handle_product_update(product_data):
                print(f"Product updated: {product_data['id']}")
        """
        def decorator(func: Callable):
            if topic not in self._handlers:
                self._handlers[topic] = []
            self._handlers[topic].append(func)
            return func
        return decorator
    
    async def handle_webhook(self, topic: str, data: Dict[str, Any]):
        """
        Process webhook event and call registered handlers.
        
        Args:
            topic: Webhook topic
            data: Webhook payload data
        """
        # Invalidate cache for the affected product
        if topic.startswith('products/'):
            product_id = str(data.get('id'))
            if product_id:
                self.adapter.invalidate_cache(product_id)
        
        # Call registered handlers
        if topic in self._handlers:
            for handler in self._handlers[topic]:
                await handler(data)
    
    def create_fastapi_app(self) -> FastAPI:
        """
        Create a FastAPI app with webhook endpoint.
        
        Returns:
            FastAPI application ready to receive webhooks
        """
        app = FastAPI(title="Shopify UCP Webhook Handler")
        
        @app.post("/webhooks/shopify")
        async def shopify_webhook(request: Request):
            """Endpoint to receive Shopify webhooks."""
            # Get headers
            hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
            topic = request.headers.get("X-Shopify-Topic", "")
            
            # Read body
            body = await request.body()
            
            # Verify signature
            if not self.verify_webhook(body, hmac_header):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature"
                )
            
            # Parse data
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON payload"
                )
            
            # Handle webhook
            await self.handle_webhook(topic, data)
            
            return {"status": "success"}
        
        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy"}
        
        return app


def create_webhook_app(config: AdapterConfig) -> FastAPI:
    """
    Convenience function to create webhook app with configuration.
    
    Args:
        config: Adapter configuration
        
    Returns:
        FastAPI app ready to run
        
    Example:
        app = create_webhook_app(config)
        
        # Run with uvicorn:
        # uvicorn app:app --host 0.0.0.0 --port 8000
    """
    adapter = ShopifyUCPAdapter(config)
    handler = WebhookHandler(adapter)
    
    # Register default handlers
    @handler.on('products/update')
    async def on_product_update(data):
        print(f"[WEBHOOK] Product updated: {data.get('id')} - {data.get('title')}")
    
    @handler.on('products/create')
    async def on_product_create(data):
        print(f"[WEBHOOK] Product created: {data.get('id')} - {data.get('title')}")
    
    @handler.on('products/delete')
    async def on_product_delete(data):
        print(f"[WEBHOOK] Product deleted: {data.get('id')}")
    
    return handler.create_fastapi_app()

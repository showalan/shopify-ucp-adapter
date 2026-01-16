"""Pydantic models for Shopify API responses."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ShopifyPrice(BaseModel):
    """Shopify price information."""
    amount: str
    currency_code: str = Field(alias="currencyCode")
    
    model_config = ConfigDict(populate_by_name=True)


class ShopifyImage(BaseModel):
    """Shopify image data."""
    id: Optional[str] = None
    url: str
    alt_text: Optional[str] = Field(None, alias="altText")
    width: Optional[int] = None
    height: Optional[int] = None
    
    model_config = ConfigDict(populate_by_name=True)


class ShopifyInventory(BaseModel):
    """Shopify inventory information."""
    available: bool
    quantity: Optional[int] = None


class ShopifyVariant(BaseModel):
    """Shopify product variant."""
    id: str
    title: str
    sku: Optional[str] = None
    price: ShopifyPrice
    compare_at_price: Optional[ShopifyPrice] = Field(None, alias="compareAtPrice")
    image: Optional[ShopifyImage] = None
    weight: Optional[float] = None
    weight_unit: Optional[str] = Field(None, alias="weightUnit")
    inventory: Optional[ShopifyInventory] = None
    available: bool = True
    selected_options: List[Dict[str, str]] = Field(default_factory=list, alias="selectedOptions")
    barcode: Optional[str] = None
    
    model_config = ConfigDict(populate_by_name=True)


class ShopifyProduct(BaseModel):
    """Shopify product data model."""
    id: str
    title: str
    description: Optional[str] = None
    description_html: Optional[str] = Field(None, alias="descriptionHtml")
    vendor: Optional[str] = None
    product_type: Optional[str] = Field(None, alias="productType")
    tags: List[str] = Field(default_factory=list)
    handle: str
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    published_at: Optional[datetime] = Field(None, alias="publishedAt")
    images: List[ShopifyImage] = Field(default_factory=list)
    variants: List[ShopifyVariant] = Field(default_factory=list)
    options: List[Dict[str, Any]] = Field(default_factory=list)
    seo_title: Optional[str] = Field(None, alias="seoTitle")
    seo_description: Optional[str] = Field(None, alias="seoDescription")
    online_store_url: Optional[str] = Field(None, alias="onlineStoreUrl")
    
    model_config = ConfigDict(populate_by_name=True)

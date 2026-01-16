"""Pydantic models for UCP/Schema.org format."""

from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class UCPOrganization(BaseModel):
    """Schema.org Organization."""
    type_: Literal["Organization"] = Field("Organization", alias="@type")
    name: str
    url: Optional[HttpUrl] = None
    
    class Config:
        populate_by_name = True


class UCPPrice(BaseModel):
    """Schema.org PriceSpecification."""
    type_: Literal["PriceSpecification"] = Field("PriceSpecification", alias="@type")
    price: str
    price_currency: str = Field(alias="priceCurrency")
    value_added_tax_included: Optional[bool] = Field(None, alias="valueAddedTaxIncluded")
    
    class Config:
        populate_by_name = True


class UCPImage(BaseModel):
    """Schema.org ImageObject."""
    type_: Literal["ImageObject"] = Field("ImageObject", alias="@type")
    url: HttpUrl
    name: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    
    class Config:
        populate_by_name = True


class UCPOffer(BaseModel):
    """Schema.org Offer - represents a product variant offer."""
    type_: Literal["Offer"] = Field("Offer", alias="@type")
    url: Optional[HttpUrl] = None
    price_specification: UCPPrice = Field(alias="priceSpecification")
    item_condition: Literal["NewCondition", "UsedCondition", "RefurbishedCondition"] = Field(
        "NewCondition", 
        alias="itemCondition"
    )
    availability: Literal[
        "InStock", 
        "OutOfStock", 
        "PreOrder", 
        "Discontinued"
    ] = Field("InStock", alias="availability")
    seller: UCPOrganization
    sku: Optional[str] = None
    gtin: Optional[str] = None  # GTIN/barcode
    mpn: Optional[str] = None  # Manufacturer Part Number
    valid_from: Optional[datetime] = Field(None, alias="validFrom")
    price_valid_until: Optional[datetime] = Field(None, alias="priceValidUntil")
    
    # Variant-specific fields
    name: Optional[str] = None  # Variant title (e.g., "Red / Large")
    
    class Config:
        populate_by_name = True


class UCPProduct(BaseModel):
    """Schema.org Product - the main UCP product representation."""
    context_: Literal["https://schema.org"] = Field("https://schema.org", alias="@context")
    type_: Literal["Product"] = Field("Product", alias="@type")
    product_id: str = Field(alias="productID")
    name: str
    description: Optional[str] = None
    image: List[UCPImage] = Field(default_factory=list)
    brand: Optional[UCPOrganization] = None
    category: Optional[str] = None
    offers: List[UCPOffer] = Field(default_factory=list)
    url: Optional[HttpUrl] = None
    
    # Additional metadata
    date_published: Optional[datetime] = Field(None, alias="datePublished")
    date_modified: Optional[datetime] = Field(None, alias="dateModified")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "@context": "https://schema.org",
                "@type": "Product",
                "productID": "gid://shopify/Product/123456",
                "name": "Premium T-Shirt",
                "description": "High quality cotton t-shirt",
                "offers": [
                    {
                        "@type": "Offer",
                        "priceSpecification": {
                            "@type": "PriceSpecification",
                            "price": "29.99",
                            "priceCurrency": "USD"
                        },
                        "availability": "InStock"
                    }
                ]
            }
        }

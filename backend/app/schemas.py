# app/schemas.py
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any

class ProductBase(BaseModel):
    sku: str
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[str] = None
    active: Optional[bool] = True
    extra: Optional[Dict[str, Any]] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    price: Optional[str]
    active: Optional[bool]
    extra: Optional[Dict[str, Any]]

class ProductOut(ProductBase):
    id: int
    class Config:
        orm_mode = True

class WebhookBase(BaseModel):
    url: HttpUrl
    events: List[str] = []
    enabled: bool = True

class WebhookOut(WebhookBase):
    id: int
    class Config:
        orm_mode = True

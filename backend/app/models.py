# app/models.py
from sqlalchemy import Column, Integer, String, Boolean, Text, UniqueConstraint, Index
from sqlalchemy.sql import func
from .database import Base
from sqlalchemy.dialects.postgresql import JSONB

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(255), nullable=False)
    sku_normalized = Column(String(255), nullable=False, unique=True, index=True)  # lower(sku)
    name = Column(String(1024), nullable=True)
    description = Column(Text, nullable=True)
    price = Column(String(64), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    extra = Column("metadata", JSONB, nullable=True)


    # Note: sku_normalized is lower(sku). We also add a unique index.

# app/crud.py
from sqlalchemy.orm import Session
from . import models, schemas
from sqlalchemy import func
from typing import List, Optional

def get_product(db: Session, product_id: int):
    return db.query(models.Product).filter(models.Product.id == product_id).first()

def get_product_by_sku(db: Session, sku: str):
    sku_norm = sku.lower()
    return db.query(models.Product).filter(models.Product.sku_normalized == sku_norm).first()

def list_products(db: Session, skip: int = 0, limit: int = 50, filters: dict = None):
    q = db.query(models.Product)
    if filters:
        if filters.get("sku"):
            q = q.filter(models.Product.sku.ilike(f"%{filters['sku']}%"))
        if filters.get("name"):
            q = q.filter(models.Product.name.ilike(f"%{filters['name']}%"))
        if filters.get("active") is not None:
            q = q.filter(models.Product.active == filters["active"])
        if filters.get("description"):
            q = q.filter(models.Product.description.ilike(f"%{filters['description']}%"))
    total = q.count()
    items = q.order_by(models.Product.id.desc()).offset(skip).limit(limit).all()
    return items, total

def create_or_update_product(db: Session, p: schemas.ProductCreate):
    sku_norm = p.sku.lower()
    obj = db.query(models.Product).filter(models.Product.sku_normalized == sku_norm).first()
    if obj:
        obj.name = p.name
        obj.description = p.description
        obj.price = p.price
        obj.active = bool(p.active) if p.active is not None else obj.active
        obj.extra = p.extra
    else:
        obj = models.Product(
            sku=p.sku,
            sku_normalized=sku_norm,
            name=p.name,
            description=p.description,
            price=p.price,
            active=bool(p.active) if p.active is not None else True,
            extra=p.extra,
        )
        db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def delete_all_products(db: Session):
    n = db.query(models.Product).delete()
    db.commit()
    return n

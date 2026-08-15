from datetime import datetime, timezone

from app import db


class Product(db.Model):
    """Maps to the `products` table from Checkpoint 1 (schema.sql)."""

    __tablename__ = 'products'

    id = db.Column('product_id', db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey('categories.category_id'), nullable=False
    )
    product_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    sku = db.Column(db.String(50), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Many-to-many with Order, through the order_items association table.
    orders = db.relationship(
        'Order', secondary='order_items', back_populates='products'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'category_id': self.category_id,
            'product_name': self.product_name,
            'description': self.description,
            'price': float(self.price) if self.price is not None else None,
            'stock_quantity': self.stock_quantity,
            'sku': self.sku,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Product id={self.id} name={self.product_name}>'

from datetime import datetime, timezone

from app import db


class Order(db.Model):
    """Maps to the `orders` table from Checkpoint 1 (schema.sql)."""

    __tablename__ = 'orders'

    id = db.Column('order_id', db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    order_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), nullable=False, default='waiting')
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    shipping_address = db.Column(db.String(255), nullable=False)

    # Many-to-many with Product, through the order_items association table.
    products = db.relationship(
        'Product', secondary='order_items', back_populates='orders'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'order_date': self.order_date.isoformat() if self.order_date else None,
            'status': self.status,
            'total_amount': float(self.total_amount) if self.total_amount is not None else None,
            'shipping_address': self.shipping_address,
        }

    def __repr__(self):
        return f'<Order id={self.id} status={self.status}>'

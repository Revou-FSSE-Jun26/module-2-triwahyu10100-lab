from app import db

# ------------------------------------------------------------
# order_items — association table implementing the many-to-many
# relationship between orders and products (Checkpoint 1 schema.sql).
#
# Defined with db.Table() rather than a full model class, per the
# checkpoint's requirement to model it as a plain association table.
# It still carries quantity/unit_price columns (matching schema.sql)
# so the price snapshot at purchase time is preserved even if a
# product's price changes later.
# ------------------------------------------------------------
order_items = db.Table(
    'order_items',
    db.Column('order_item_id', db.Integer, primary_key=True),
    db.Column(
        'order_id',
        db.Integer,
        db.ForeignKey('orders.order_id', ondelete='CASCADE'),
        nullable=False,
    ),
    db.Column(
        'product_id',
        db.Integer,
        db.ForeignKey('products.product_id', ondelete='RESTRICT'),
        nullable=False,
    ),
    db.Column('quantity', db.Integer, nullable=False),
    db.Column('unit_price', db.Numeric(10, 2), nullable=False),
    db.UniqueConstraint('order_id', 'product_id', name='uq_order_product'),
)

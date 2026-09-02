from app import db

# ------------------------------------------------------------
# order_items — tabel asosiasi yang mengimplementasikan relasi
# many-to-many antara orders dan products (Checkpoint 1 schema.sql).
#
# Didefinisikan dengan db.Table(), bukan class model penuh, sesuai
# syarat checkpoint untuk memodelkannya sebagai tabel asosiasi murni.
# Tetap menyimpan kolom quantity/unit_price (sesuai schema.sql) supaya
# snapshot harga saat pembelian tetap tersimpan, walau harga produk
# berubah di kemudian hari.
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

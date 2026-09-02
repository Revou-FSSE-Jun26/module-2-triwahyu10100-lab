from datetime import datetime, timezone

from app import db


class Product(db.Model):
    """Terhubung ke tabel `products` dari Checkpoint 1 (schema.sql)."""

    __tablename__ = 'products'

    id = db.Column('product_id', db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey('categories.category_id'), nullable=False
    )
    product_name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(180), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    sku = db.Column(db.String(50), nullable=False, unique=True)

    # Daftar URL gambar, contoh: ["https://.../1.jpg", "https://.../2.jpg"].
    # Disimpan sebagai JSON supaya bekerja sama baiknya di Postgres
    # (production) dan SQLite (TestConfig in-memory milik pytest).
    images = db.Column(db.JSON, nullable=False, default=list)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    # Penanda soft-delete. NULL = produk aktif. Produk tidak pernah
    # dihapus permanen begitu punya histori order, jadi ini
    # membolehkan katalog "menghapus" produk tanpa merusak histori
    # order/order_items.
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Many-to-many dengan Order, lewat tabel asosiasi order_items.
    orders = db.relationship(
        'Order', secondary='order_items', back_populates='products'
    )

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def to_dict(self):
        return {
            'id': self.id,
            'category_id': self.category_id,
            'product_name': self.product_name,
            'slug': self.slug,
            'description': self.description,
            'price': float(self.price) if self.price is not None else None,
            'stock_quantity': self.stock_quantity,
            'sku': self.sku,
            'images': self.images or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self):
        return f'<Product id={self.id} name={self.product_name}>'

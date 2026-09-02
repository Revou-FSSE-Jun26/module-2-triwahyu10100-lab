from datetime import datetime, timezone

from app import db


class Category(db.Model):
    """Terhubung ke tabel `categories` dari Checkpoint 1 (schema.sql)."""

    __tablename__ = 'categories'

    id = db.Column('category_id', db.Integer, primary_key=True)
    category_name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    products = db.relationship('Product', backref='category', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'category_name': self.category_name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Category id={self.id} name={self.category_name}>'

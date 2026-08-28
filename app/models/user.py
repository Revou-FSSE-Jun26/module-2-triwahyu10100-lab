from datetime import datetime, timezone

from app import db


class User(db.Model):
    """
    Maps to the `users` table created in Checkpoint 1 (schema.sql).

    Checkpoint 1 shipped this table with first_name/last_name instead of a
    single `username`. Checkpoint 2's spec calls for `username`, so it is
    added here as a new nullable column (see migrations/) rather than
    dropping the existing name fields — this keeps the Checkpoint 1 seed
    data intact while satisfying the new model shape.

    `role` was added in a dedicated follow-up migration (see
    migrations/versions/), per the checkpoint's requirement to practice
    `flask db migrate` / `flask db upgrade` for a schema change.
    """

    __tablename__ = 'users'

    id = db.Column('user_id', db.Integer, primary_key=True)

    # New column added via migration for Checkpoint 2 (see migrations history).
    username = db.Column(db.String(50), unique=True, nullable=True)

    # Carried over from the Checkpoint 1 schema.
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(255), nullable=True)

    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Added via migration for Checkpoint 2 (see migrations/versions/).
    # server_default ensures existing rows are backfilled with 'customer'
    # instead of ending up NULL when the column is introduced.
    role = db.Column(db.String(20), nullable=False, server_default='customer')

    # Soft-delete marker. NULL = active account. Users are never hard
    # deleted once they have order history, so this "deactivates" an
    # account without breaking the FK on orders.user_id.
    deleted_at = db.Column(db.DateTime, nullable=True)

    orders = db.relationship('Order', backref='user', lazy=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self):
        return f'<User id={self.id} email={self.email}>'

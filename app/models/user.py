from datetime import datetime, timezone

from app import db


class User(db.Model):
    """
    Terhubung ke tabel `users` yang dibuat di Checkpoint 1 (schema.sql).

    Checkpoint 1 awalnya membuat tabel ini dengan first_name/last_name,
    bukan satu kolom `username`. Spesifikasi Checkpoint 2 meminta ada
    `username`, jadi kolom ini ditambahkan sebagai kolom baru yang boleh
    kosong/nullable (lihat migrations/), bukan dengan menghapus kolom
    nama yang sudah ada — supaya data seed dari Checkpoint 1 tetap utuh,
    sekaligus memenuhi bentuk model yang baru.

    Kolom `role` ditambahkan lewat migrasi terpisah susulan (lihat
    migrations/versions/), sesuai syarat checkpoint untuk berlatih
    menjalankan `flask db migrate` / `flask db upgrade` saat ada
    perubahan skema.
    """

    __tablename__ = 'users'

    id = db.Column('user_id', db.Integer, primary_key=True)

    # Kolom baru yang ditambahkan lewat migrasi untuk Checkpoint 2 (lihat histori migrations).
    username = db.Column(db.String(50), unique=True, nullable=True)

    # Dibawa dari skema Checkpoint 1.
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(255), nullable=True)

    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Ditambahkan lewat migrasi untuk Checkpoint 2 (lihat migrations/versions/).
    # server_default memastikan baris yang sudah ada terisi otomatis
    # dengan 'customer', bukan malah jadi NULL saat kolom ini diperkenalkan.
    role = db.Column(db.String(20), nullable=False, server_default='customer')

    # Penanda soft-delete. NULL = akun aktif. User tidak pernah dihapus
    # permanen begitu punya histori order, jadi ini "menonaktifkan"
    # akun tanpa merusak FK pada orders.user_id.
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

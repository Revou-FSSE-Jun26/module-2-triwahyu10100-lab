"""
Schema Marshmallow untuk validasi body request.

Schema-schema ini menggantikan validasi "bentuk data" yang dulu ditulis
manual di dalam masing-masing route (cek keberadaan field, tipe data,
rentang angka, struktur list) — lihat PANDUAN_BELAJAR_CODING.md dan
VALIDASI_DAN_STATUS_CODE.md untuk perbandingan lengkap sebelum/sesudahnya.

Ada dua jenis pengecekan yang sengaja TIDAK dimasukkan ke schema ini,
tetap ditaruh di route-nya sendiri:

- Pengecekan duplikat/unik yang harus mengecualikan "data yang sedang
  diupdate itu sendiri" (sku, category_name, username, email).
  marshmallow versi 4.x sudah menghapus mekanisme Schema.context lama
  yang biasa dipakai untuk hal semacam ini (lihat bagian "Upgrading to
  4.0" pada dokumentasi marshmallow), dan tidak ada penggantinya yang
  cocok untuk pengecualian satu id secara rapi. Menaruh pengecekan ini
  di route — tepat setelah schema.load() berhasil — lebih sederhana dan
  membuat schema tetap fokus hanya ke bentuk data.
- Aturan bisnis antar-tabel/tergantung kondisi yang bukan soal bentuk
  satu field saja (misal "apakah stoknya cukup", "apakah order ini boleh
  diubah isinya sekarang"). Itu semua tetap ada di route/fungsi helper,
  tidak berubah dari sebelumnya.

Pola penggunaan di setiap route yang memakai schema ini:

    try:
        validated = SomeSchema().load(data)          # atau load(data, partial=True) untuk PUT
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

`err.messages` berupa dict `{nama_field: [pesan_error, ...]}`, bukan
string biasa — ini perbedaan yang disengaja dari validasi manual di
bagian lain API ini (yang selalu mengembalikan satu string di bawah key
`error`). Lihat VALIDASI_DAN_STATUS_CODE.md untuk alasan trade-off ini
diterima, alih-alih meratakannya kembali jadi string.
"""
from marshmallow import Schema, fields, validate, validates, ValidationError

from app.models.category import Category
from app.models.product import Product

__all__ = [
    'CategorySchema',
    'ProductSchema',
    'OrderItemSchema',
    'OrderCreateSchema',
    'UserRegisterSchema',
    'UserUpdateSchema',
    'LoginSchema',
    'ValidationError',
]


class CategorySchema(Schema):
    """Dipakai untuk POST /categories maupun PUT /categories/<id> (pakai load(..., partial=True) untuk yang PUT)."""

    class Meta:
        # Key yang tidak dikenal di body akan diam-diam diabaikan,
        # bukan ditolak — sesuai perilaku lama, di mana route hanya
        # pernah membaca field spesifik yang dibutuhkannya dari `data`.
        unknown = 'EXCLUDE'

    category_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, error='category_name cannot be empty'),
    )
    description = fields.Str(allow_none=True)


class ProductSchema(Schema):
    """
    Dipakai untuk POST /products maupun PUT /products/<id> (yang PUT
    pakai partial=True).

    Dengan sengaja TIDAK memvalidasi keunikan `sku` (karena perlu
    mengecualikan produk yang sedang diupdate) atau membuat `slug` (itu
    tetap jadi tanggung jawab product_routes.py, memakai
    slugify()/_resolve_unique_slug() seperti sebelumnya) — keduanya
    tetap ditangani di route setelah schema.load().
    """

    class Meta:
        unknown = 'EXCLUDE'

    category_id = fields.Int(required=True)
    product_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, error='product_name cannot be empty'),
    )
    # slug bersifat opsional, dan kalau diisi akan di-slugify ulang oleh
    # route — ini hanya menjaga supaya tidak ada string kosong yang dikirim.
    slug = fields.Str(allow_none=True, validate=validate.Length(min=1, error='slug cannot be empty'))
    description = fields.Str(allow_none=True)
    price = fields.Float(
        required=True,
        validate=validate.Range(min=0, error='price must be greater than or equal to 0'),
    )
    stock_quantity = fields.Int(
        validate=validate.Range(min=0, error='stock_quantity must be greater than or equal to 0'),
    )
    sku = fields.Str(required=True, validate=validate.Length(min=1, error='sku cannot be empty'))
    images = fields.List(
        fields.Str(validate=validate.Length(min=1, error='must be a non-empty string')),
        validate=validate.Length(max=10, error='images cannot contain more than 10 URLs'),
    )

    @validates('category_id')
    def validate_category_id_exists(self, value, data_key):
        """
        Pengecekan referensi: hanya berjalan kalau category_id memang
        ada di input (jadi otomatis di-skip pada PUT sebagian yang tidak
        menyentuh category_id). Tidak perlu pengecualian diri sendiri di
        sini — berbeda dengan keunikan sku, category_id sebuah produk
        tidak pernah bisa "konflik" dengan dirinya sendiri.
        """
        if Category.query.get(value) is None:
            raise ValidationError(f'Category with id {value} does not exist')


class OrderItemSchema(Schema):
    """Satu baris item di dalam list `items` milik OrderCreateSchema."""

    class Meta:
        unknown = 'EXCLUDE'

    product_id = fields.Int(required=True)
    quantity = fields.Int(
        required=True,
        validate=validate.Range(min=1, error='quantity must be greater than 0'),
    )


class OrderCreateSchema(Schema):
    """
    Dipakai untuk POST /orders. Hanya memvalidasi bentuk body request —
    pengecekan product_id duplikat antar baris, keberadaan produk, dan
    ketersediaan stok adalah pengecekan antar-tabel/tergantung kondisi
    yang tetap ditaruh di fungsi helper _validate_and_resolve_items() di
    order_routes.py, dijalankan tepat setelah schema ini berhasil (lihat
    komentar di sana untuk alasannya).
    """

    class Meta:
        unknown = 'EXCLUDE'

    shipping_address = fields.Str(
        required=True,
        validate=validate.Length(min=1, error='shipping_address cannot be empty'),
    )
    items = fields.List(
        fields.Nested(OrderItemSchema),
        required=True,
        validate=validate.Length(min=1, error='items must be a non-empty list'),
    )


class UserRegisterSchema(Schema):
    """Dipakai untuk POST /users. Tidak mengecek keunikan email/username — lihat docstring modul di atas."""

    class Meta:
        unknown = 'EXCLUDE'

    first_name = fields.Str(required=True, validate=validate.Length(min=1, error='first_name cannot be empty'))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, error='last_name cannot be empty'))
    email = fields.Email(required=True, error_messages={'invalid': 'email must be a valid email address'})
    password = fields.Str(required=True, validate=validate.Length(min=1, error='password cannot be empty'))
    username = fields.Str(allow_none=True)
    phone = fields.Str(allow_none=True)
    address = fields.Str(allow_none=True)


class UserUpdateSchema(Schema):
    """Dipakai untuk PUT /users/<id> (pakai partial=True). Sengaja tidak menyertakan email/password — lihat docstring di route-nya."""

    class Meta:
        unknown = 'EXCLUDE'

    username = fields.Str(allow_none=True)
    phone = fields.Str(allow_none=True)
    address = fields.Str(allow_none=True)


class LoginSchema(Schema):
    """Dipakai untuk POST /auth/login."""

    class Meta:
        unknown = 'EXCLUDE'

    email = fields.Email(required=True, error_messages={'invalid': 'email must be a valid email address'})
    password = fields.Str(required=True, validate=validate.Length(min=1, error='password cannot be empty'))

"""
Fungsi bantuan yang dipakai bersama oleh semua modul route: pembuatan
slug, dan pembacaan parameter query secara umum (pagination + sorting)
untuk endpoint yang menampilkan daftar data.
"""
import re


def slugify(text):
    """
    Mengubah sebuah teks menjadi slug: aman untuk URL, huruf kecil semua,
    dipisah tanda hubung.

    Contoh: "Wireless Bluetooth Headphones!" -> "wireless-bluetooth-headphones"
    """
    text = text.strip().lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = re.sub(r'-{2,}', '-', text)
    return text.strip('-')


def parse_pagination(args, default_per_page=20, max_per_page=100):
    """
    Membaca `page` dan `per_page` dari query string permintaan (objek
    MultiDict dari werkzeug, contohnya `request.args`).

    Mengembalikan (page, per_page, error). `error` berisi teks penjelasan
    kalau ada yang salah, atau None kalau kedua nilai valid. Nilai yang
    di luar batas wajar akan dibatasi otomatis (bukan langsung ditolak),
    kecuali kalau memang bukan angka bulat sama sekali.
    """
    page_raw = args.get('page', '1')
    per_page_raw = args.get('per_page', str(default_per_page))

    try:
        page = int(page_raw)
    except ValueError:
        return None, None, 'page must be an integer'

    try:
        per_page = int(per_page_raw)
    except ValueError:
        return None, None, 'per_page must be an integer'

    if page < 1:
        return None, None, 'page must be greater than or equal to 1'
    if per_page < 1:
        return None, None, 'per_page must be greater than or equal to 1'

    per_page = min(per_page, max_per_page)
    return page, per_page, None


def parse_sort(args, allowed_fields, default='created_at', default_direction='desc'):
    """
    Membaca parameter query `sort`, contohnya `sort=price` atau
    `sort=-price` (tanda `-` di depan berarti urutan menurun/descending).
    Mengembalikan (field, direction, error).

    `allowed_fields` adalah daftar nama kolom yang aman untuk dipakai
    sebagai patokan sorting (dibatasi/whitelist supaya tidak bisa sorting
    berdasarkan kolom sembarangan yang tidak seharusnya bisa diakses).
    """
    sort_raw = args.get('sort', None)
    if not sort_raw:
        return default, default_direction, None

    direction = 'desc' if sort_raw.startswith('-') else 'asc'
    field = sort_raw.lstrip('-')

    if field not in allowed_fields:
        return None, None, f'sort must be one of: {", ".join(sorted(allowed_fields))} (optionally prefixed with -)'

    return field, direction, None


def paginate_query(query, page, per_page):
    """
    Menerapkan pagination (offset/limit) ke sebuah query SQLAlchemy, dan
    mengembalikan dict berisi hasil halaman tersebut plus informasi
    metadata pagination-nya (total data, total halaman, dll).
    """
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page if per_page else 0

    return {
        'items': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_items': total,
            'total_pages': total_pages,
        },
    }

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models.order import Order
from app.models.order_item import order_items
from app.models.product import Product
from app.models.user import User
from app.schemas import OrderCreateSchema, ValidationError
from app.utils import paginate_query, parse_pagination, parse_sort

order_bp = Blueprint('orders', __name__, url_prefix='/orders')

VALID_ORDER_STATUSES = ('waiting', 'paid', 'shipped', 'delivered', 'cancelled')

# Transisi status yang diperbolehkan, mengikuti alur checkout marketplace
# pada umumnya (lihat misalnya https://fakeapi.platzi.com/en/rest/products/
# sebagai referensi skema marketplace). 'waiting' berperan sebagai status
# "menunggu": order sudah dibuat tapi belum dibayar.
#
#   waiting  -> paid       (pembayaran sukses, lihat POST /orders/<id>/pay)
#   waiting  -> cancelled  (pembeli/penjual membatalkan sebelum bayar)
#   paid     -> shipped    (penjual mengirim barang)
#   paid     -> cancelled  (refund sebelum barang dikirim)
#   shipped  -> delivered  (barang sampai ke pembeli)
#   delivered / cancelled  -> status akhir, tidak ada transisi lagi
#
# Membatalkan dari status 'waiting' atau 'paid' akan mengembalikan stok
# setiap item; begitu order sudah 'shipped', barang fisik sedang dalam
# pengiriman dan tidak bisa lagi dibatalkan lewat API ini.
ORDER_TRANSITIONS = {
    'waiting': {'paid', 'cancelled'},
    'paid': {'shipped', 'cancelled'},
    'shipped': {'delivered'},
    'delivered': set(),
    'cancelled': set(),
}

# Status-status yang stoknya sudah direservasi untuk order dan belum
# dikembalikan ke inventori. Dipakai untuk memutuskan apakah
# membatalkan/menghapus sebuah order perlu mengembalikan stok item-nya.
STOCK_RESERVED_STATUSES = ('waiting', 'paid')

# Kolom yang boleh dipakai client untuk sorting GET /orders.
SORTABLE_FIELDS = {'order_date', 'total_amount', 'status'}


# ------------------------------------------------------------------ helpers
def _order_items_for(order_id):
    """
    Mengembalikan baris-baris order_items untuk sebuah order, digabung
    dengan tabel produk supaya pemanggilnya dapat product_name selain
    quantity/unit_price.
    """
    rows = (
        db.session.query(order_items, Product.product_name)
        .join(Product, Product.id == order_items.c.product_id)
        .filter(order_items.c.order_id == order_id)
        .all()
    )
    return [
        {
            'order_item_id': row.order_item_id,
            'product_id': row.product_id,
            'product_name': row.product_name,
            'quantity': row.quantity,
            'unit_price': float(row.unit_price),
            'subtotal': float(row.unit_price) * row.quantity,
        }
        for row in rows
    ]


def _order_to_dict(order, include_items=False):
    data = order.to_dict()
    if include_items:
        data['items'] = _order_items_for(order.id)
    return data


def _validate_and_resolve_items(items_payload):
    """
    Memvalidasi payload `items` dari POST/PUT terhadap database dan
    mengembalikan (resolved_items, error). Setiap item hasil resolusi
    berbentuk {'product': <Product>, 'quantity': <int>}.

    Harga sengaja tidak pernah dibaca dari body request — selalu
    diambil dari `product.price` di database, supaya client tidak bisa
    melapor harga lebih rendah/tinggi dari aslinya.
    """
    if not isinstance(items_payload, list) or len(items_payload) == 0:
        return None, 'items must be a non-empty list'

    resolved_items = []
    seen_product_ids = set()
    for idx, item in enumerate(items_payload):
        if not isinstance(item, dict) or 'product_id' not in item or 'quantity' not in item:
            return None, f'items[{idx}] must contain product_id and quantity'

        try:
            quantity = int(item['quantity'])
        except (TypeError, ValueError):
            return None, f'items[{idx}].quantity must be an integer'
        if quantity <= 0:
            return None, f'items[{idx}].quantity must be greater than 0'

        if item['product_id'] in seen_product_ids:
            return None, f'items[{idx}] duplicates product_id {item["product_id"]}; combine into a single line item'
        seen_product_ids.add(item['product_id'])

        product = Product.query.get(item['product_id'])
        if product is None or product.is_deleted:
            return None, f'Product with id {item["product_id"]} does not exist'
        if product.stock_quantity < quantity:
            return None, (
                f'Not enough stock for product "{product.product_name}" '
                f'(requested {quantity}, available {product.stock_quantity})'
            )

        resolved_items.append({'product': product, 'quantity': quantity})

    return resolved_items, None


def _insert_order_items(order_id, resolved_items):
    """Memasukkan baris order_items dan mengurangi stok untuk setiap item yang sudah diresolusi."""
    for ri in resolved_items:
        product = ri['product']
        db.session.execute(
            order_items.insert().values(
                order_id=order_id,
                product_id=product.id,
                quantity=ri['quantity'],
                unit_price=product.price,
            )
        )
        product.stock_quantity -= ri['quantity']


def _restock_order_items(order_id):
    """
    Mengembalikan stok ke setiap produk yang terkait sebuah order
    (dipakai saat order dibatalkan atau dihapus ketika stoknya masih
    ter-reservasi).
    """
    rows = db.session.query(order_items).filter(order_items.c.order_id == order_id).all()
    for row in rows:
        product = Product.query.get(row.product_id)
        if product is not None:
            product.stock_quantity += row.quantity


# --------------------------------------------------------------------- GET
@order_bp.route('', methods=['GET'])
@jwt_required()
def list_orders():
    """
    GET /orders — menampilkan daftar order milik user yang sedang login
    sendiri (diidentifikasi lewat JWT, bukan user_id yang dikirim
    client — user tidak akan pernah bisa melihat daftar order milik
    user lain). Parameter query opsional:

    - status: filter berdasarkan status persis
    - min_total / max_total: filter berdasarkan rentang total_amount
    - sort: kolom pengurutan, misal 'total_amount' atau '-order_date'.
            Diperbolehkan: order_date, total_amount, status
    - page / per_page: pagination (default page=1, per_page=20, maks 100)
    """
    current_user_id = int(get_jwt_identity())
    query = Order.query.filter_by(user_id=current_user_id)

    status = request.args.get('status')
    if status is not None:
        if status not in VALID_ORDER_STATUSES:
            return jsonify({'error': f'status must be one of: {", ".join(VALID_ORDER_STATUSES)}'}), 400
        query = query.filter_by(status=status)

    for param, op in (('min_total', 'ge'), ('max_total', 'le')):
        raw = request.args.get(param)
        if raw is not None:
            try:
                value = float(raw)
            except ValueError:
                return jsonify({'error': f'{param} must be a number'}), 400
            query = query.filter(Order.total_amount >= value) if op == 'ge' else query.filter(Order.total_amount <= value)

    sort_field, sort_direction, error = parse_sort(request.args, SORTABLE_FIELDS, default='order_date')
    if error:
        return jsonify({'error': error}), 400
    column = getattr(Order, sort_field)
    query = query.order_by(column.desc() if sort_direction == 'desc' else column.asc())

    page, per_page, error = parse_pagination(request.args)
    if error:
        return jsonify({'error': error}), 400

    result = paginate_query(query, page, per_page)
    return jsonify({
        'items': [_order_to_dict(o) for o in result['items']],
        'pagination': result['pagination'],
    }), 200


@order_bp.route('/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order(order_id):
    """
    GET /orders/<id> — mengembalikan satu order lengkap dengan item dan
    detail produknya. Hanya pemilik order (sesuai identitas JWT) yang
    boleh melihatnya; siapapun selain itu mendapat 404 — API ini tidak
    pernah membocorkan bahwa order dengan id tersebut milik orang lain.
    """
    order = Order.query.get(order_id)
    if order is None or order.user_id != int(get_jwt_identity()):
        return jsonify({'error': f'Order with id {order_id} not found'}), 404
    return jsonify(_order_to_dict(order, include_items=True)), 200


# -------------------------------------------------------------------- POST
@order_bp.route('', methods=['POST'])
@jwt_required()
def create_order():
    """
    POST /orders — membuat order baru untuk user yang sedang login.

    Membutuhkan JWT yang valid (Authorization: Bearer <access_token>).
    Pemilik order selalu identitas dari token — `user_id` tidak lagi
    diterima dari body request, jadi client tidak akan pernah bisa
    membuat order atas nama user lain.

    Contoh body JSON yang diharapkan:
    {
        "shipping_address": "Jl. Merdeka No. 10, Jakarta",
        "items": [
            {"product_id": 2, "quantity": 3},
            {"product_id": 5, "quantity": 1}
        ]
    }

    Aturan bisnis yang dipaksakan di sisi server (tidak pernah dipercaya
    dari request):
    - Stok setiap produk harus mencukupi jumlah yang diminta.
    - unit_price dibaca dari products.price di database, bukan dari body
      request — client tidak bisa mengirim harganya sendiri.
    - total_amount dihitung oleh backend dari unit price yang sudah
      diresolusi, tidak diterima dari body request.
    - Stok langsung dikurangi supaya jumlah yang sudah direservasi tidak
      bisa terjual dua kali selagi order masih menunggu pembayaran.
    """
    current_user_id = int(get_jwt_identity())
    user = User.query.get(current_user_id)
    if user is None or user.is_deleted:
        return jsonify({'error': 'Your account could not be found; please log in again'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = OrderCreateSchema().load(data)
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

    resolved_items, error = _validate_and_resolve_items(validated['items'])
    if error:
        return jsonify({'error': error}), 400

    # total_amount seluruhnya diturunkan dari harga di database — tidak pernah dari body request.
    total_amount = sum(float(ri['product'].price) * ri['quantity'] for ri in resolved_items)

    try:
        new_order = Order(
            user_id=current_user_id,
            shipping_address=validated['shipping_address'],
            status='waiting',
            total_amount=total_amount,
        )
        db.session.add(new_order)
        db.session.flush()  # assign new_order.id without committing yet

        _insert_order_items(new_order.id, resolved_items)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not create order: {str(e)}'}), 500

    return jsonify(_order_to_dict(new_order, include_items=True)), 201


# --------------------------------------------------------------------- PUT
@order_bp.route('/<int:order_id>', methods=['PUT'])
@jwt_required()
def update_order(order_id):
    """
    PUT /orders/<id> — mengubah order yang sudah ada. Hanya subset
    field tertentu yang bisa diubah di sini (bukan penggantian total):

    {
        "status": "cancelled",              # opsional, transisi divalidasi
        "shipping_address": "New address",  # opsional
        "items": [                          # opsional, mengganti seluruh daftar item
            {"product_id": 2, "quantity": 1}
        ]
    }

    Aturan:
    - status harus mengikuti graf transisi yang diperbolehkan (waiting ->
      paid -> shipped -> delivered, dengan pembatalan dari waiting/paid).
      Membatalkan akan mengembalikan stok setiap item pada order.
    - shipping_address hanya bisa diubah sebelum order dikirim
      (waiting/paid) — begitu sudah shipped, paketnya sudah dalam
      perjalanan.
    - items (produk/qty) hanya bisa diubah selama order masih 'waiting'
      (yaitu sebelum pembayaran). Mengubah item akan mengembalikan
      jumlah lama, memvalidasi daftar baru terhadap stok saat ini,
      lalu mengurangi stok lagi dan menghitung ulang total_amount dari
      harga di database.

    Membutuhkan JWT yang valid; hanya pemilik order sendiri yang boleh
    mengubahnya — semua yang lain mendapat 404 (keberadaan order tidak
    dibocorkan ke yang bukan pemiliknya).
    """
    order = Order.query.get(order_id)
    if order is None or order.user_id != int(get_jwt_identity()):
        return jsonify({'error': f'Order with id {order_id} not found'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    allowed_fields = {'status', 'shipping_address', 'items'}
    unknown_fields = set(data.keys()) - allowed_fields
    if unknown_fields:
        return jsonify({
            'error': f'These fields cannot be updated via PUT /orders/<id>: {", ".join(sorted(unknown_fields))}'
        }), 400

    new_status = None
    if 'status' in data:
        new_status = data['status']
        if new_status not in VALID_ORDER_STATUSES:
            return jsonify({'error': f'status must be one of: {", ".join(VALID_ORDER_STATUSES)}'}), 400
        if new_status != order.status and new_status not in ORDER_TRANSITIONS[order.status]:
            return jsonify({
                'error': f'Cannot transition order from "{order.status}" to "{new_status}"'
            }), 409

    if 'shipping_address' in data:
        if not data['shipping_address']:
            return jsonify({'error': 'shipping_address cannot be empty'}), 400
        if order.status not in ('waiting', 'paid'):
            return jsonify({
                'error': f'Cannot change shipping_address once an order is "{order.status}"'
            }), 409

    resolved_items = None
    if 'items' in data:
        if order.status != 'waiting':
            return jsonify({
                'error': 'Order items can only be changed while the order is "waiting" (not yet paid)'
            }), 409
        # Kembalikan stok item saat ini secara sementara, supaya daftar
        # baru divalidasi terhadap stok yang benar-benar tersedia (unit
        # yang sudah direservasi order ini dikembalikan ke pool dulu).
        _restock_order_items(order.id)
        resolved_items, error = _validate_and_resolve_items(data['items'])
        if error:
            db.session.rollback()
            return jsonify({'error': error}), 400

    try:
        if resolved_items is not None:
            db.session.execute(order_items.delete().where(order_items.c.order_id == order.id))
            _insert_order_items(order.id, resolved_items)
            order.total_amount = sum(float(ri['product'].price) * ri['quantity'] for ri in resolved_items)

        if new_status is not None and new_status != order.status:
            if new_status == 'cancelled' and order.status in STOCK_RESERVED_STATUSES:
                _restock_order_items(order.id)
            order.status = new_status

        if 'shipping_address' in data:
            order.shipping_address = data['shipping_address']

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not update order: {str(e)}'}), 500

    return jsonify(_order_to_dict(order, include_items=True)), 200


# ------------------------------------------------------------ POST /pay
@order_bp.route('/<int:order_id>/pay', methods=['POST'])
@jwt_required()
def pay_order(order_id):
    """
    POST /orders/<id>/pay — mensimulasikan callback dari payment
    gateway: kalau sukses, order bertransisi dari 'waiting' langsung ke
    'paid'.

    Contoh body JSON (opsional):
    { "payment_method": "credit_card" }

    Membutuhkan JWT yang valid; hanya pemilik order sendiri yang boleh
    membayarnya.

    Endpoint ini tidak menyentuh stok — stok sudah direservasi saat
    order dibuat (POST /orders). Ini hanya mengubah status setelah
    transisinya valid.
    """
    order = Order.query.get(order_id)
    if order is None or order.user_id != int(get_jwt_identity()):
        return jsonify({'error': f'Order with id {order_id} not found'}), 404

    if order.status != 'waiting':
        return jsonify({
            'error': f'Cannot pay an order that is "{order.status}" (must be "waiting")'
        }), 409

    try:
        order.status = 'paid'
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not mark order as paid: {str(e)}'}), 500

    return jsonify(_order_to_dict(order, include_items=True)), 200


# ------------------------------------------------------------------ DELETE
@order_bp.route('/<int:order_id>', methods=['DELETE'])
@jwt_required()
def delete_order(order_id):
    """
    DELETE /orders/<id> — menghapus sebuah order.

    Membutuhkan JWT yang valid; hanya pemilik order sendiri yang boleh
    menghapusnya.

    Hanya diperbolehkan selama order masih 'waiting' (belum ada yang
    dibayar atau dikirim — stok otomatis dikembalikan sebelum
    penghapusan) atau sudah 'cancelled' (stok sudah dikembalikan saat
    dibatalkan; ini cuma membersihkan datanya). Order yang 'paid',
    'shipped', atau 'delivered' adalah bagian dari histori
    finansial/pengiriman dan tidak bisa dihapus — batalkan dulu order
    yang sudah dibayar (PUT status=cancelled) kalau masih memenuhi
    syarat.
    """
    order = Order.query.get(order_id)
    if order is None or order.user_id != int(get_jwt_identity()):
        return jsonify({'error': f'Order with id {order_id} not found'}), 404

    if order.status not in ('waiting', 'cancelled'):
        return jsonify({
            'error': f'Cannot delete an order that is "{order.status}"; cancel it first if eligible'
        }), 409

        
    try:
        if order.status in STOCK_RESERVED_STATUSES:
            _restock_order_items(order.id)
        db.session.delete(order)  # baris order_items ikut terhapus otomatis via ON DELETE CASCADE
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not delete order: {str(e)}'}), 500

    return jsonify({'message': f'Order with id {order_id} deleted successfully'}), 200

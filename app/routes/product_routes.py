from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app import db
from app.models.order import Order
from app.models.order_item import order_items
from app.models.product import Product
from app.schemas import ProductSchema, ValidationError
from app.utils import paginate_query, parse_pagination, parse_sort, slugify

product_bp = Blueprint('products', __name__, url_prefix='/products')

# Order statuses that count as "active" — a product still tied to one of
# these via order_items cannot be deleted. 'delivered' and 'cancelled' are
# considered final states, so a product is free to be deleted afterwards.
ACTIVE_ORDER_STATUSES = ('waiting', 'paid', 'shipped')

# Columns the client is allowed to sort GET /products by (whitelisted to
# avoid sorting by arbitrary/unmapped attributes).
SORTABLE_FIELDS = {'price', 'product_name', 'created_at', 'stock_quantity'}


def _resolve_unique_slug(base_slug, *, exclude_product_id=None):
    """
    Ensures a slug is unique by appending -2, -3, ... if the base slug
    (or a fully custom one from the client) is already taken.
    """
    slug = base_slug
    suffix = 2
    while True:
        query = Product.query.filter_by(slug=slug)
        if exclude_product_id is not None:
            query = query.filter(Product.id != exclude_product_id)
        if query.first() is None:
            return slug
        slug = f'{base_slug}-{suffix}'
        suffix += 1


@product_bp.route('', methods=['GET'])
def list_products():
    """
    GET /products — lists products, with optional query parameters:

    - category_id: filter by category
    - min_price / max_price: filter by price range
    - search: case-insensitive substring match on product_name
    - include_deleted: 'true' to include soft-deleted products (default: excluded)
    - sort: column to sort by, e.g. 'price' (asc) or '-price' (desc).
            Allowed: price, product_name, created_at, stock_quantity
    - page / per_page: pagination (default page=1, per_page=20, max 100)
    """
    query = Product.query

    include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'
    if not include_deleted:
        query = query.filter(Product.deleted_at.is_(None))

    category_id = request.args.get('category_id')
    if category_id is not None:
        try:
            category_id = int(category_id)
        except ValueError:
            return jsonify({'error': 'category_id must be an integer'}), 400
        query = query.filter(Product.category_id == category_id)

    for param, op in (('min_price', 'ge'), ('max_price', 'le')):
        raw = request.args.get(param)
        if raw is not None:
            try:
                value = float(raw)
            except ValueError:
                return jsonify({'error': f'{param} must be a number'}), 400
            query = query.filter(Product.price >= value) if op == 'ge' else query.filter(Product.price <= value)

    search = request.args.get('search')
    if search:
        query = query.filter(Product.product_name.ilike(f'%{search}%'))

    sort_field, sort_direction, error = parse_sort(request.args, SORTABLE_FIELDS)
    if error:
        return jsonify({'error': error}), 400
    column = getattr(Product, sort_field)
    query = query.order_by(column.desc() if sort_direction == 'desc' else column.asc())

    page, per_page, error = parse_pagination(request.args)
    if error:
        return jsonify({'error': error}), 400

    result = paginate_query(query, page, per_page)
    return jsonify({
        'items': [p.to_dict() for p in result['items']],
        'pagination': result['pagination'],
    }), 200


@product_bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """GET /products/<id> — returns a single product by id."""
    product = Product.query.get(product_id)
    if product is None:
        return jsonify({'error': f'Product with id {product_id} not found'}), 404
    return jsonify(product.to_dict()), 200


@product_bp.route('', methods=['POST'])
def create_product():
    """
    POST /products — creates a new product.

    Expected JSON body:
    {
        "category_id": 1,
        "product_name": "Wireless Mouse",
        "slug": "wireless-mouse",                      # optional, auto-generated from product_name if omitted
        "description": "Ergonomic wireless mouse",     # optional
        "price": 199000.00,
        "stock_quantity": 40,                          # optional, default 0
        "sku": "ELEC-MOUS-004",
        "images": ["https://.../1.jpg"]                 # optional, default []
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = ProductSchema().load(data)
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

    if Product.query.filter_by(sku=validated['sku']).first():
        return jsonify({'error': 'A product with this sku already exists'}), 409

    base_slug = slugify(validated['slug']) if validated.get('slug') else slugify(validated['product_name'])
    if not base_slug:
        return jsonify({'error': 'Could not derive a valid slug from product_name/slug'}), 400
    slug = _resolve_unique_slug(base_slug)

    try:
        new_product = Product(
            category_id=validated['category_id'],
            product_name=validated['product_name'],
            slug=slug,
            description=validated.get('description'),
            price=validated['price'],
            stock_quantity=validated.get('stock_quantity', 0),
            sku=validated['sku'],
            images=validated.get('images', []),
        )
        db.session.add(new_product)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not create product: {str(e)}'}), 500

    return jsonify(new_product.to_dict()), 201


@product_bp.route('/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """
    PUT /products/<id> — updates an existing product.

    Accepts a partial JSON body; only the fields provided are updated.
    """
    product = Product.query.get(product_id)
    if product is None:
        return jsonify({'error': f'Product with id {product_id} not found'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = ProductSchema().load(data, partial=True)
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

    if 'sku' in validated and validated['sku'] != product.sku:
        existing = Product.query.filter_by(sku=validated['sku']).first()
        if existing:
            return jsonify({'error': 'A product with this sku already exists'}), 409

    new_slug = None
    if 'slug' in validated and validated.get('slug'):
        base_slug = slugify(validated['slug'])
        if not base_slug:
            return jsonify({'error': 'Could not derive a valid slug from slug'}), 400
        if base_slug != product.slug:
            new_slug = _resolve_unique_slug(base_slug, exclude_product_id=product.id)

    try:
        for field in ('category_id', 'product_name', 'description', 'price', 'stock_quantity', 'sku', 'images'):
            if field in validated:
                setattr(product, field, validated[field])
        if new_slug:
            product.slug = new_slug
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not update product: {str(e)}'}), 500

    return jsonify(product.to_dict()), 200


@product_bp.route('/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """
    DELETE /products/<id> — soft-deletes a product (sets deleted_at),
    unless it is linked to an order that is still active (status in
    waiting/paid/shipped). The row stays in the database so existing
    order/order_items history remains intact; it just disappears from
    the default GET /products listing (see include_deleted).
    """
    product = Product.query.get(product_id)
    if product is None:
        return jsonify({'error': f'Product with id {product_id} not found'}), 404

    if product.is_deleted:
        return jsonify({'error': f'Product with id {product_id} was already deleted'}), 409

    has_active_order = (
        db.session.query(order_items)
        .join(Order, Order.id == order_items.c.order_id)
        .filter(
            order_items.c.product_id == product_id,
            Order.status.in_(ACTIVE_ORDER_STATUSES),
        )
        .first()
    )
    if has_active_order:
        return jsonify({
            'error': 'Cannot delete product: it is linked to one or more active orders'
        }), 409

    try:
        product.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not delete product: {str(e)}'}), 500

    return jsonify({'message': f'Product with id {product_id} deleted successfully'}), 200

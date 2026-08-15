from flask import Blueprint, jsonify

product_bp = Blueprint('products', __name__, url_prefix='/products')

# ------------------------------------------------------------
# Warm-up data: hardcoded products, no database involved yet.
# Structured as a list of dicts with consistent, meaningful
# keys so it can later map cleanly onto the Product model.
# ------------------------------------------------------------
PRODUCTS = [
    {
        'id': 1,
        'name': 'Wireless Bluetooth Headphones',
        'description': 'Over-ear headphones with active noise cancellation',
        'price': 799000.00,
        'stock_quantity': 50,
        'sku': 'ELEC-HEAD-001',
    },
    {
        'id': 2,
        'name': 'USB-C Fast Charger 65W',
        'description': 'GaN fast charger compatible with laptops and phones',
        'price': 249000.00,
        'stock_quantity': 120,
        'sku': 'ELEC-CHRG-002',
    },
    {
        'id': 3,
        'name': 'Mechanical Keyboard RGB',
        'description': 'Tactile switches with per-key RGB lighting',
        'price': 550000.00,
        'stock_quantity': 35,
        'sku': 'ELEC-KEYB-003',
    },
    {
        'id': 4,
        'name': 'Cotton Crewneck T-Shirt',
        'description': 'Unisex 100% cotton t-shirt, various colors',
        'price': 89000.00,
        'stock_quantity': 200,
        'sku': 'APRL-TSHT-001',
    },
    {
        'id': 5,
        'name': 'Denim Jacket',
        'description': 'Classic fit denim jacket for men and women',
        'price': 349000.00,
        'stock_quantity': 60,
        'sku': 'APRL-JCKT-002',
    },
]


@product_bp.route('', methods=['GET'])
def list_products():
    """GET /products — returns the full hardcoded product list as JSON."""
    return jsonify(PRODUCTS), 200


@product_bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """GET /products/<id> — returns a single hardcoded product by id."""
    product = next((p for p in PRODUCTS if p['id'] == product_id), None)
    if product is None:
        return jsonify({'error': f'Product with id {product_id} not found'}), 404
    return jsonify(product), 200

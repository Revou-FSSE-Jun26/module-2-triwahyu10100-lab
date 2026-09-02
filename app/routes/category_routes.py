from flask import Blueprint, jsonify, request

from app import db
from app.models.category import Category
from app.schemas import CategorySchema, ValidationError

category_bp = Blueprint('categories', __name__, url_prefix='/categories')


@category_bp.route('', methods=['GET'])
def list_categories():
    """GET /categories — mengembalikan semua baris kategori sebagai JSON."""
    categories = Category.query.all()
    return jsonify([c.to_dict() for c in categories]), 200


@category_bp.route('/<int:category_id>', methods=['GET'])
def get_category(category_id):
    """
    GET /categories/<id> — mengembalikan satu kategori beserta daftar
    produk yang termasuk di dalamnya.
    """
    category = Category.query.get(category_id)
    if category is None:
        return jsonify({'error': f'Category with id {category_id} not found'}), 404

    data = category.to_dict()
    data['products'] = [p.to_dict() for p in category.products]
    return jsonify(data), 200


@category_bp.route('', methods=['POST'])
def create_category():
    """
    POST /categories — membuat kategori baru.

    Contoh body JSON yang diharapkan:
    {
        "category_name": "Electronics",
        "description": "Gadgets and accessories"   # opsional
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = CategorySchema().load(data)
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

    if Category.query.filter_by(category_name=validated['category_name']).first():
        return jsonify({'error': 'A category with this name already exists'}), 409

    try:
        new_category = Category(
            category_name=validated['category_name'],
            description=validated.get('description'),
        )
        db.session.add(new_category)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not create category: {str(e)}'}), 500

    return jsonify(new_category.to_dict()), 201


@category_bp.route('/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    """
    PUT /categories/<id> — mengubah kategori yang sudah ada.

    Menerima body JSON sebagian; hanya field yang dikirim yang akan
    diubah.
    """
    category = Category.query.get(category_id)
    if category is None:
        return jsonify({'error': f'Category with id {category_id} not found'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = CategorySchema().load(data, partial=True)
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

    if 'category_name' in validated and validated['category_name'] != category.category_name:
        existing = Category.query.filter_by(category_name=validated['category_name']).first()
        if existing:
            return jsonify({'error': 'A category with this name already exists'}), 409

    try:
        for field in ('category_name', 'description'):
            if field in validated:
                setattr(category, field, validated[field])
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not update category: {str(e)}'}), 500

    return jsonify(category.to_dict()), 200


@category_bp.route('/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """
    DELETE /categories/<id> — menghapus sebuah kategori.

    Ditolak (409) kalau kategori itu masih punya produk yang terhubung,
    karena products.category_id bersifat NOT NULL dan FK di database
    memakai ON DELETE RESTRICT.
    """
    category = Category.query.get(category_id)
    if category is None:
        return jsonify({'error': f'Category with id {category_id} not found'}), 404

    if category.products:
        return jsonify({
            'error': 'Cannot delete category: it still has products linked to it'
        }), 409

    try:
        db.session.delete(category)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not delete category: {str(e)}'}), 500

    return jsonify({'message': f'Category with id {category_id} deleted successfully'}), 200

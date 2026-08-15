from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from app import db
from app.models.user import User

user_bp = Blueprint('users', __name__, url_prefix='/users')


@user_bp.route('/register', methods=['POST'])
def register_user():
    """
    POST /users/register — creates a new User row in the database.

    Expected JSON body:
    {
        "username": "budi123",
        "first_name": "Budi",
        "last_name": "Santoso",
        "email": "budi@example.com",
        "phone": "+62-812-0000-0000",   # optional
        "password": "plaintext-password"
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    required_fields = ['first_name', 'last_name', 'email', 'password']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing required field(s): {", ".join(missing)}'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'A user with this email already exists'}), 409

    username = data.get('username')
    if username and User.query.filter_by(username=username).first():
        return jsonify({'error': 'A user with this username already exists'}), 409

    new_user = User(
        username=username,
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        phone=data.get('phone'),
        password_hash=generate_password_hash(data['password']),
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify(new_user.to_dict()), 201


@user_bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """GET /users/<id> — retrieves a single user by id, or 404 if absent."""
    user = User.query.get(user_id)
    if user is None:
        return jsonify({'error': f'User with id {user_id} not found'}), 404
    return jsonify(user.to_dict()), 200

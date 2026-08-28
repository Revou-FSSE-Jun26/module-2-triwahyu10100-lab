from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models.user import User
from app.schemas import LoginSchema, UserRegisterSchema, UserUpdateSchema, ValidationError

user_bp = Blueprint('users', __name__, url_prefix='/users')
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@user_bp.route('', methods=['POST'])
def register_user():
    """
    POST /users — creates a new User row in the database.

    Expected JSON body:
    {
        "username": "budi123",
        "first_name": "Budi",
        "last_name": "Santoso",
        "email": "budi@example.com",
        "phone": "+62-812-0000-0000",           # optional
        "address": "Jl. Merdeka No. 10, Jakarta", # optional
        "password": "plaintext-password"
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = UserRegisterSchema().load(data)
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

    if User.query.filter_by(email=validated['email']).first():
        return jsonify({'error': 'A user with this email already exists'}), 409

    username = validated.get('username')
    if username and User.query.filter_by(username=username).first():
        return jsonify({'error': 'A user with this username already exists'}), 409

    try:
        new_user = User(
            username=username,
            first_name=validated['first_name'],
            last_name=validated['last_name'],
            email=validated['email'],
            phone=validated.get('phone'),
            address=validated.get('address'),
            password_hash=generate_password_hash(validated['password']),
        )
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not create user: {str(e)}'}), 500

    return jsonify(new_user.to_dict()), 201


@user_bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """
    GET /users/<id> — retrieves a single user by id.

    Returns 404 both when the id doesn't exist and when the account has
    been soft-deleted — from the API consumer's point of view a
    deactivated account should look the same as one that was never there.
    """
    user = User.query.get(user_id)
    if user is None or user.is_deleted:
        return jsonify({'error': f'User with id {user_id} not found'}), 404
    return jsonify(user.to_dict()), 200


@user_bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    """
    PUT /users/<id> — updates a user's own profile fields.

    Requires a valid JWT (Authorization: Bearer <access_token>) obtained
    from POST /auth/login. The token's identity must match `user_id` in
    the URL — a logged-in user can only update their own profile, never
    someone else's, even if they know that user's id.

    Accepts a partial JSON body; only phone/address/username can be
    changed here — email and password are intentionally left out of this
    endpoint's scope (changing credentials would need re-verification,
    which is outside what Module 2 covers).
    """
    if int(get_jwt_identity()) != user_id:
        return jsonify({'error': 'You can only update your own account'}), 403

    user = User.query.get(user_id)
    if user is None or user.is_deleted:
        return jsonify({'error': f'User with id {user_id} not found'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = UserUpdateSchema().load(data, partial=True)
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

    if 'username' in validated and validated['username']:
        existing = User.query.filter_by(username=validated['username']).first()
        if existing and existing.id != user.id:
            return jsonify({'error': 'A user with this username already exists'}), 409

    try:
        for field in ('username', 'phone', 'address'):
            if field in validated:
                setattr(user, field, validated[field])
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not update user: {str(e)}'}), 500

    return jsonify(user.to_dict()), 200


@user_bp.route('/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    """
    DELETE /users/<id> — soft-deletes a user account (sets deleted_at).

    Requires a valid JWT whose identity matches `user_id` — a user can
    only deactivate their own account, never someone else's.

    The row is kept so existing orders (orders.user_id has no ON DELETE
    CASCADE) remain valid; the account just becomes unable to log in or
    be looked up going forward.
    """
    if int(get_jwt_identity()) != user_id:
        return jsonify({'error': 'You can only delete your own account'}), 403

    user = User.query.get(user_id)
    if user is None or user.is_deleted:
        return jsonify({'error': f'User with id {user_id} not found'}), 404

    try:
        user.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Could not delete user: {str(e)}'}), 500

    return jsonify({'message': f'User with id {user_id} deleted successfully'}), 200


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    POST /auth/login — verifies email/password and issues a JWT access
    token for the account.

    Expected JSON body:
    {
        "email": "budi@example.com",
        "password": "plaintext-password"
    }

    Response body:
    {
        "access_token": "<JWT>",
        "user": { ...same shape as GET /users/<id>... }
    }

    The client must send `access_token` as a Bearer token
    (`Authorization: Bearer <access_token>`) on every subsequent request
    to an endpoint protected with @jwt_required() — e.g. POST /orders,
    PUT/DELETE /users/<id>. There is no separate refresh-token flow: once
    the token expires (see JWT_ACCESS_TOKEN_EXPIRES in config.py), the
    client must call this endpoint again.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = LoginSchema().load(data)
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

    user = User.query.filter_by(email=validated['email']).first()
    if (
        user is None
        or user.is_deleted
        or not check_password_hash(user.password_hash, validated['password'])
    ):
        # Deliberately the same generic message for "no such user",
        # "wrong password", and "deactivated account" — this avoids
        # leaking which emails are registered or deactivated.
        return jsonify({'error': 'Invalid email or password'}), 401

    # The JWT "identity" is the subject the token vouches for. It's kept
    # as a string (flask-jwt-extended's recommended practice) and turned
    # back into an int via get_jwt_identity() wherever it's consumed.
    access_token = create_access_token(identity=str(user.id))

    return jsonify({'access_token': access_token, 'user': user.to_dict()}), 200

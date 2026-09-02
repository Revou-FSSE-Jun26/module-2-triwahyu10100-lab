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
    POST /users — membuat baris User baru di database.

    Contoh body JSON yang diharapkan:
    {
        "username": "budi123",
        "first_name": "Budi",
        "last_name": "Santoso",
        "email": "budi@example.com",
        "phone": "+62-812-0000-0000",           # opsional
        "address": "Jl. Merdeka No. 10, Jakarta", # opsional
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
    GET /users/<id> — mengambil satu user berdasarkan id.

    Mengembalikan 404 baik saat id-nya memang tidak ada, maupun saat
    akun itu sudah soft-delete — dari sudut pandang pengguna API, akun
    yang sudah dinonaktifkan harus terlihat sama seperti akun yang
    memang tidak pernah ada.
    """
    user = User.query.get(user_id)
    if user is None or user.is_deleted:
        return jsonify({'error': f'User with id {user_id} not found'}), 404
    return jsonify(user.to_dict()), 200


@user_bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    """
    PUT /users/<id> — mengubah field profil milik user sendiri.

    Membutuhkan JWT yang valid (Authorization: Bearer <access_token>)
    yang didapat dari POST /auth/login. Identitas token harus sama
    dengan `user_id` di URL — user yang sedang login hanya bisa
    mengubah profilnya sendiri, tidak pernah milik orang lain, walau
    dia tahu id user tersebut.

    Menerima body JSON sebagian; hanya phone/address/username yang bisa
    diubah di sini — email dan password sengaja tidak dimasukkan ke
    lingkup endpoint ini (mengubah kredensial memerlukan verifikasi
    ulang, yang di luar cakupan Modul 2).
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
    DELETE /users/<id> — soft-delete akun user (mengisi deleted_at).

    Membutuhkan JWT valid yang identitasnya sama dengan `user_id` — user
    hanya bisa menonaktifkan akunnya sendiri, tidak pernah akun orang
    lain.

    Baris datanya tetap dipertahankan supaya order-order yang sudah ada
    (kolom orders.user_id tidak punya ON DELETE CASCADE) tetap valid;
    akunnya cuma jadi tidak bisa login atau dicari lagi ke depannya.
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
    POST /auth/login — memverifikasi email/password dan menerbitkan JWT
    access token untuk akun tersebut.

    Contoh body JSON yang diharapkan:
    {
        "email": "budi@example.com",
        "password": "plaintext-password"
    }

    Contoh body response:
    {
        "access_token": "<JWT>",
        "user": { ...bentuknya sama seperti GET /users/<id>... }
    }

    Client harus mengirim `access_token` sebagai Bearer token
    (`Authorization: Bearer <access_token>`) pada setiap request
    berikutnya ke endpoint yang dilindungi @jwt_required() — misalnya
    POST /orders, PUT/DELETE /users/<id>. Tidak ada mekanisme
    refresh-token terpisah: begitu token expired (lihat
    JWT_ACCESS_TOKEN_EXPIRES di config.py), client harus memanggil
    endpoint ini lagi.
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
        # Sengaja pakai pesan generik yang sama untuk "user tidak ada",
        # "password salah", dan "akun sudah dinonaktifkan" — ini
        # menghindari kebocoran informasi soal email mana yang
        # terdaftar atau sudah dinonaktifkan.
        return jsonify({'error': 'Invalid email or password'}), 401

    # "identity" pada JWT adalah subjek yang dijamin oleh token
    # tersebut. Disimpan sebagai string (sesuai praktik yang
    # direkomendasikan flask-jwt-extended), dan diubah balik jadi
    # integer lewat get_jwt_identity() di setiap tempat yang memakainya.
    access_token = create_access_token(identity=str(user.id))

    return jsonify({'access_token': access_token, 'user': user.to_dict()}), 200

"""
Tests for the User/Auth module: registration with the new address field,
login, and the soft-delete lifecycle (PUT to update profile fields,
DELETE to deactivate, and the resulting lockout from GET/login).
"""
from app.models.user import User


def _register(client, email='budi@example.com', **overrides):
    payload = {
        'first_name': 'Budi',
        'last_name': 'Santoso',
        'email': email,
        'password': 'pass123',
    }
    payload.update(overrides)
    return client.post('/users', json=payload)


# ---------------------------------------------------------------- POST /users
def test_register_user_with_address(client):
    response = _register(client, address='Jl. Merdeka No. 1, Jakarta')

    assert response.status_code == 201
    assert response.get_json()['address'] == 'Jl. Merdeka No. 1, Jakarta'


def test_register_user_missing_fields(client):
    response = client.post('/users', json={'email': 'a@b.com'})

    assert response.status_code == 400


def test_register_user_duplicate_email(client):
    _register(client, email='dup@example.com')

    response = _register(client, email='dup@example.com')

    assert response.status_code == 409


# ---------------------------------------------------------------- POST /auth/login
def test_login_happy_path(client):
    _register(client, email='budi@example.com')

    response = client.post('/auth/login', json={'email': 'budi@example.com', 'password': 'pass123'})

    assert response.status_code == 200
    body = response.get_json()
    assert body['user']['email'] == 'budi@example.com'
    assert isinstance(body['access_token'], str) and len(body['access_token']) > 0


def test_login_wrong_password(client):
    _register(client, email='budi@example.com')

    response = client.post('/auth/login', json={'email': 'budi@example.com', 'password': 'wrong'})

    assert response.status_code == 401


def test_login_unknown_email(client):
    response = client.post('/auth/login', json={'email': 'nobody@example.com', 'password': 'pass123'})

    assert response.status_code == 401


# ---------------------------------------------------------------- GET /users/<id>
def test_get_user_not_found(client):
    response = client.get('/users/999')

    assert response.status_code == 404


# ---------------------------------------------------------------- PUT /users/<id>
def test_update_user_happy_path(client, auth_header):
    user_id = _register(client).get_json()['id']

    response = client.put(
        f'/users/{user_id}',
        json={'phone': '0812-0000-0000', 'address': 'New address'},
        headers=auth_header(user_id),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body['phone'] == '0812-0000-0000'
    assert body['address'] == 'New address'


def test_update_user_not_found(client, auth_header):
    response = client.put('/users/999', json={'phone': '0812'}, headers=auth_header(999))

    assert response.status_code == 404


def test_update_user_requires_auth(client):
    user_id = _register(client).get_json()['id']

    response = client.put(f'/users/{user_id}', json={'phone': '0812'})

    assert response.status_code == 401


def test_update_user_cannot_edit_another_account(client, auth_header):
    user_id = _register(client, email='victim@example.com').get_json()['id']
    other_id = _register(client, email='attacker@example.com').get_json()['id']

    response = client.put(f'/users/{user_id}', json={'phone': '0812'}, headers=auth_header(other_id))

    assert response.status_code == 403


# ---------------------------------------------------------------- DELETE /users/<id>
def test_delete_user_soft_deletes(client, db, auth_header):
    user_id = _register(client).get_json()['id']

    response = client.delete(f'/users/{user_id}', headers=auth_header(user_id))

    assert response.status_code == 200
    user = User.query.get(user_id)
    assert user is not None  # row is kept, not hard-deleted
    assert user.deleted_at is not None


def test_delete_user_not_found(client, auth_header):
    response = client.delete('/users/999', headers=auth_header(999))

    assert response.status_code == 404


def test_delete_user_requires_auth(client):
    user_id = _register(client).get_json()['id']

    response = client.delete(f'/users/{user_id}')

    assert response.status_code == 401


def test_deleted_user_cannot_be_fetched(client, auth_header):
    user_id = _register(client, email='gone@example.com').get_json()['id']
    client.delete(f'/users/{user_id}', headers=auth_header(user_id))

    response = client.get(f'/users/{user_id}')

    assert response.status_code == 404


def test_deleted_user_cannot_login(client, auth_header):
    user_id = _register(client, email='gone@example.com').get_json()['id']
    client.delete(f'/users/{user_id}', headers=auth_header(user_id))

    response = client.post('/auth/login', json={'email': 'gone@example.com', 'password': 'pass123'})

    assert response.status_code == 401

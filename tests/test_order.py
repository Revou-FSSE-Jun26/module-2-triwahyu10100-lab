"""
Tests for the Order module: stock-safe creation (price/total always
computed server-side), the status transition graph, the payment
endpoint, restocking on cancel/delete, restricted PUT item edits,
GET /orders filtering/sorting/pagination, and the JWT-based ownership
rules (every order endpoint requires the owner's own access token).
"""
from app.models.order import Order


def _place_order(client, auth_header, user, product, quantity=1, **overrides):
    payload = {
        'shipping_address': 'Jl. Merdeka No. 1',
        'items': [{'product_id': product.id, 'quantity': quantity}],
    }
    payload.update(overrides)
    return client.post('/orders', json=payload, headers=auth_header(user))


# ---------------------------------------------------------------- POST
def test_create_order_happy_path(client, db, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10, price=100000.00)

    response = _place_order(client, auth_header, user, product, quantity=3)

    assert response.status_code == 201
    body = response.get_json()
    assert body['status'] == 'waiting'
    assert body['total_amount'] == 300000.00
    assert len(body['items']) == 1
    assert body['items'][0]['quantity'] == 3
    assert body['items'][0]['unit_price'] == 100000.00

    db.session.refresh(product)
    assert product.stock_quantity == 7


def test_create_order_requires_auth(client, make_product):
    product = make_product(stock=10)

    response = client.post('/orders', json={
        'shipping_address': 'Jl. Merdeka No. 1',
        'items': [{'product_id': product.id, 'quantity': 1}],
    })

    assert response.status_code == 401


def test_create_order_ignores_price_from_request_body(client, db, auth_header, make_user, make_product):
    """Price/total must always come from the DB, never from the client."""
    user = make_user()
    product = make_product(stock=10, price=1000.00)

    response = client.post('/orders', json={
        'shipping_address': 'Jl. Merdeka No. 1',
        'items': [{'product_id': product.id, 'quantity': 2, 'price': 1}],
    }, headers=auth_header(user))

    assert response.status_code == 201
    body = response.get_json()
    # 2 * real DB price (1000), not 2 * spoofed price (1)
    assert body['total_amount'] == 2000.00
    assert body['items'][0]['unit_price'] == 1000.00


def test_create_order_missing_fields(client, auth_header, make_user):
    user = make_user()

    response = client.post('/orders', json={}, headers=auth_header(user))

    assert response.status_code == 400


def test_create_order_insufficient_stock(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=1)

    response = _place_order(client, auth_header, user, product, quantity=5)

    assert response.status_code == 400


def test_create_order_duplicate_product_line_rejected(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)

    response = client.post('/orders', json={
        'shipping_address': 'Jl. Merdeka No. 1',
        'items': [
            {'product_id': product.id, 'quantity': 1},
            {'product_id': product.id, 'quantity': 2},
        ],
    }, headers=auth_header(user))

    assert response.status_code == 400


def test_create_order_token_for_nonexistent_user(client, auth_header, make_product):
    """A syntactically valid JWT whose identity has no matching user row."""
    product = make_product(stock=10)

    response = client.post('/orders', json={
        'shipping_address': 'Jl. Merdeka No. 1',
        'items': [{'product_id': product.id, 'quantity': 1}],
    }, headers=auth_header(999))

    assert response.status_code == 404


# ---------------------------------------------------------------- GET
def test_get_order_happy_path(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product()
    create_resp = _place_order(client, auth_header, user, product, quantity=2)
    order_id = create_resp.get_json()['id']

    response = client.get(f'/orders/{order_id}', headers=auth_header(user))

    assert response.status_code == 200
    assert response.get_json()['items'][0]['product_id'] == product.id


def test_get_order_not_found(client, auth_header, make_user):
    user = make_user()

    response = client.get('/orders/999', headers=auth_header(user))

    assert response.status_code == 404


def test_get_order_requires_auth(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product()
    order_id = _place_order(client, auth_header, user, product).get_json()['id']

    response = client.get(f'/orders/{order_id}')

    assert response.status_code == 401


def test_get_order_hides_other_users_order(client, auth_header, make_user, make_product):
    """A different logged-in user must not be able to view someone else's order."""
    owner = make_user(email='owner@example.com')
    other = make_user(email='other@example.com')
    product = make_product()
    order_id = _place_order(client, auth_header, owner, product).get_json()['id']

    response = client.get(f'/orders/{order_id}', headers=auth_header(other))

    assert response.status_code == 404


def test_list_orders_only_returns_own_orders(client, auth_header, make_user, make_product):
    owner = make_user(email='owner@example.com')
    other = make_user(email='other@example.com')
    product = make_product()
    _place_order(client, auth_header, owner, product)

    owner_resp = client.get('/orders', headers=auth_header(owner))
    other_resp = client.get('/orders', headers=auth_header(other))

    assert owner_resp.get_json()['pagination']['total_items'] == 1
    assert other_resp.get_json()['pagination']['total_items'] == 0


def test_list_orders_filtered_by_status(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    resp = _place_order(client, auth_header, user, product)
    order_id = resp.get_json()['id']
    client.post(f'/orders/{order_id}/pay', headers=auth_header(user))

    waiting_resp = client.get('/orders?status=waiting', headers=auth_header(user))
    paid_resp = client.get('/orders?status=paid', headers=auth_header(user))

    assert waiting_resp.get_json()['pagination']['total_items'] == 0
    assert paid_resp.get_json()['pagination']['total_items'] == 1


def test_list_orders_invalid_status_filter(client, auth_header, make_user):
    user = make_user()

    response = client.get('/orders?status=bogus', headers=auth_header(user))

    assert response.status_code == 400


# ---------------------------------------------------------------- pay
def test_pay_order_happy_path(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, user, product).get_json()['id']

    response = client.post(f'/orders/{order_id}/pay', headers=auth_header(user))

    assert response.status_code == 200
    assert response.get_json()['status'] == 'paid'


def test_pay_order_not_found(client, auth_header, make_user):
    user = make_user()

    response = client.post('/orders/999/pay', headers=auth_header(user))

    assert response.status_code == 404


def test_pay_order_already_paid(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, user, product).get_json()['id']
    client.post(f'/orders/{order_id}/pay', headers=auth_header(user))

    response = client.post(f'/orders/{order_id}/pay', headers=auth_header(user))

    assert response.status_code == 409


def test_pay_order_blocked_for_non_owner(client, auth_header, make_user, make_product):
    owner = make_user(email='owner@example.com')
    other = make_user(email='other@example.com')
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, owner, product).get_json()['id']

    response = client.post(f'/orders/{order_id}/pay', headers=auth_header(other))

    assert response.status_code == 404


# ---------------------------------------------------------------- PUT (status transitions)
def test_update_order_invalid_transition(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, user, product).get_json()['id']

    # waiting -> shipped directly is not allowed; must go through 'paid' first.
    response = client.put(f'/orders/{order_id}', json={'status': 'shipped'}, headers=auth_header(user))

    assert response.status_code == 409


def test_update_order_full_happy_path_transition(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, user, product).get_json()['id']

    client.post(f'/orders/{order_id}/pay', headers=auth_header(user))
    ship_resp = client.put(f'/orders/{order_id}', json={'status': 'shipped'}, headers=auth_header(user))
    deliver_resp = client.put(f'/orders/{order_id}', json={'status': 'delivered'}, headers=auth_header(user))

    assert ship_resp.status_code == 200
    assert ship_resp.get_json()['status'] == 'shipped'
    assert deliver_resp.status_code == 200
    assert deliver_resp.get_json()['status'] == 'delivered'


def test_update_order_cancel_from_waiting_restocks(client, db, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, user, product, quantity=4).get_json()['id']
    db.session.refresh(product)
    assert product.stock_quantity == 6

    response = client.put(f'/orders/{order_id}', json={'status': 'cancelled'}, headers=auth_header(user))

    assert response.status_code == 200
    db.session.refresh(product)
    assert product.stock_quantity == 10


def test_update_order_cannot_cancel_after_shipped(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, user, product).get_json()['id']
    client.post(f'/orders/{order_id}/pay', headers=auth_header(user))
    client.put(f'/orders/{order_id}', json={'status': 'shipped'}, headers=auth_header(user))

    response = client.put(f'/orders/{order_id}', json={'status': 'cancelled'}, headers=auth_header(user))

    assert response.status_code == 409


def test_update_order_reject_unknown_field(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, user, product).get_json()['id']

    response = client.put(f'/orders/{order_id}', json={'user_id': 999}, headers=auth_header(user))

    assert response.status_code == 400


def test_update_order_shipping_address_blocked_after_shipped(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, user, product).get_json()['id']
    client.post(f'/orders/{order_id}/pay', headers=auth_header(user))
    client.put(f'/orders/{order_id}', json={'status': 'shipped'}, headers=auth_header(user))

    response = client.put(
        f'/orders/{order_id}', json={'shipping_address': 'New address'}, headers=auth_header(user),
    )

    assert response.status_code == 409


def test_update_order_blocked_for_non_owner(client, auth_header, make_user, make_product):
    owner = make_user(email='owner@example.com')
    other = make_user(email='other@example.com')
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, owner, product).get_json()['id']

    response = client.put(f'/orders/{order_id}', json={'status': 'cancelled'}, headers=auth_header(other))

    assert response.status_code == 404


# ---------------------------------------------------------------- PUT (item edits)
def test_update_order_items_while_waiting(client, db, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10, price=1000.00)
    order_id = _place_order(client, auth_header, user, product, quantity=2).get_json()['id']
    db.session.refresh(product)
    assert product.stock_quantity == 8

    response = client.put(f'/orders/{order_id}', json={
        'items': [{'product_id': product.id, 'quantity': 5}],
    }, headers=auth_header(user))

    assert response.status_code == 200
    assert response.get_json()['total_amount'] == 5000.00
    db.session.refresh(product)
    assert product.stock_quantity == 5


def test_update_order_items_blocked_after_paid(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, user, product).get_json()['id']
    client.post(f'/orders/{order_id}/pay', headers=auth_header(user))

    response = client.put(f'/orders/{order_id}', json={
        'items': [{'product_id': product.id, 'quantity': 1}],
    }, headers=auth_header(user))

    assert response.status_code == 409


# ---------------------------------------------------------------- DELETE
def test_delete_order_waiting_restocks_and_deletes(client, db, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, user, product, quantity=3).get_json()['id']

    response = client.delete(f'/orders/{order_id}', headers=auth_header(user))

    assert response.status_code == 200
    assert Order.query.count() == 0
    db.session.refresh(product)
    assert product.stock_quantity == 10


def test_delete_order_not_found(client, auth_header, make_user):
    user = make_user()

    response = client.delete('/orders/999', headers=auth_header(user))

    assert response.status_code == 404


def test_delete_order_blocked_when_paid(client, auth_header, make_user, make_product):
    user = make_user()
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, user, product).get_json()['id']
    client.post(f'/orders/{order_id}/pay', headers=auth_header(user))

    response = client.delete(f'/orders/{order_id}', headers=auth_header(user))

    assert response.status_code == 409


def test_delete_order_blocked_for_non_owner(client, auth_header, make_user, make_product):
    owner = make_user(email='owner@example.com')
    other = make_user(email='other@example.com')
    product = make_product(stock=10)
    order_id = _place_order(client, auth_header, owner, product).get_json()['id']

    response = client.delete(f'/orders/{order_id}', headers=auth_header(other))

    assert response.status_code == 404

"""
CRUD tests for the Product module: slug/images handling, the soft-delete
guard blocking removal of a product still linked to an active order, and
the filter/sort/pagination query parameters on GET /products.
"""
from app.models.order import Order
from app.models.order_item import order_items
from app.models.product import Product


# ---------------------------------------------------------------- GET (list)
def test_list_products_happy_path(client, make_product):
    make_product(sku='SKU-1')

    response = client.get('/products')

    assert response.status_code == 200
    body = response.get_json()
    assert body['pagination']['total_items'] == 1
    assert len(body['items']) == 1


def test_list_products_excludes_soft_deleted_by_default(client, make_product):
    product = make_product(sku='SKU-1')
    client.delete(f'/products/{product.id}')

    response = client.get('/products')

    assert response.status_code == 200
    assert response.get_json()['pagination']['total_items'] == 0


def test_list_products_include_deleted_flag(client, make_product):
    product = make_product(sku='SKU-1')
    client.delete(f'/products/{product.id}')

    response = client.get('/products?include_deleted=true')

    assert response.status_code == 200
    assert response.get_json()['pagination']['total_items'] == 1


def test_list_products_filter_by_category(client, make_category, make_product):
    cat_a = make_category(name='A')
    cat_b = make_category(name='B')
    make_product(category_id=cat_a.id, name='In A', sku='SKU-A')
    make_product(category_id=cat_b.id, name='In B', sku='SKU-B')

    response = client.get(f'/products?category_id={cat_a.id}')

    assert response.status_code == 200
    items = response.get_json()['items']
    assert len(items) == 1
    assert items[0]['sku'] == 'SKU-A'


def test_list_products_price_range_filter(client, make_product):
    make_product(name='Cheap', sku='SKU-CHEAP', price=1000)
    make_product(name='Expensive', sku='SKU-EXP', price=100000)

    response = client.get('/products?min_price=5000')

    assert response.status_code == 200
    items = response.get_json()['items']
    assert len(items) == 1
    assert items[0]['sku'] == 'SKU-EXP'


def test_list_products_search(client, make_product):
    make_product(name='Wireless Mouse', sku='SKU-1')
    make_product(name='Mechanical Keyboard', sku='SKU-2')

    response = client.get('/products?search=mouse')

    assert response.status_code == 200
    items = response.get_json()['items']
    assert len(items) == 1
    assert items[0]['sku'] == 'SKU-1'


def test_list_products_sort_desc(client, make_product):
    make_product(name='Cheap', sku='SKU-CHEAP', price=1000)
    make_product(name='Expensive', sku='SKU-EXP', price=100000)

    response = client.get('/products?sort=-price')

    assert response.status_code == 200
    items = response.get_json()['items']
    assert [p['sku'] for p in items] == ['SKU-EXP', 'SKU-CHEAP']


def test_list_products_invalid_sort_field(client, make_product):
    response = client.get('/products?sort=bogus_field')

    assert response.status_code == 400


def test_list_products_pagination(client, make_product):
    for i in range(5):
        make_product(name=f'Product {i}', sku=f'SKU-{i}')

    response = client.get('/products?page=2&per_page=2')

    assert response.status_code == 200
    body = response.get_json()
    assert len(body['items']) == 2
    assert body['pagination'] == {'page': 2, 'per_page': 2, 'total_items': 5, 'total_pages': 3}


def test_list_products_invalid_page(client, make_product):
    response = client.get('/products?page=0')

    assert response.status_code == 400


# ---------------------------------------------------------------- GET (one)
def test_get_product_not_found(client):
    response = client.get('/products/999')

    assert response.status_code == 404


# ---------------------------------------------------------------- POST
def test_create_product_happy_path(client, make_category):
    category = make_category()

    response = client.post('/products', json={
        'category_id': category.id,
        'product_name': 'USB-C Charger',
        'price': 249000.00,
        'stock_quantity': 100,
        'sku': 'ELEC-CHRG-001',
        'images': ['https://example.com/1.jpg', 'https://example.com/2.jpg'],
    })

    assert response.status_code == 201
    body = response.get_json()
    assert body['sku'] == 'ELEC-CHRG-001'
    assert body['slug'] == 'usb-c-charger'
    assert body['images'] == ['https://example.com/1.jpg', 'https://example.com/2.jpg']
    assert Product.query.count() == 1


def test_create_product_auto_slug_dedup(client, make_category):
    category = make_category()
    payload = {
        'category_id': category.id,
        'product_name': 'Wireless Mouse',
        'price': 1000,
        'sku': 'SKU-1',
    }
    client.post('/products', json=payload)

    payload['sku'] = 'SKU-2'
    response = client.post('/products', json=payload)

    assert response.status_code == 201
    assert response.get_json()['slug'] == 'wireless-mouse-2'


def test_create_product_missing_fields(client):
    response = client.post('/products', json={'product_name': 'No category or price'})

    assert response.status_code == 400


def test_create_product_invalid_category(client):
    response = client.post('/products', json={
        'category_id': 999,
        'product_name': 'Orphan Product',
        'price': 10000,
        'sku': 'X-001',
    })

    assert response.status_code == 400


def test_create_product_negative_price(client, make_category):
    category = make_category()

    response = client.post('/products', json={
        'category_id': category.id,
        'product_name': 'Bad Price Product',
        'price': -5,
        'sku': 'X-002',
    })

    assert response.status_code == 400


def test_create_product_duplicate_sku(client, make_product):
    product = make_product(sku='DUP-001')

    response = client.post('/products', json={
        'category_id': product.category_id,
        'product_name': 'Another Product',
        'price': 1000,
        'sku': 'DUP-001',
    })

    assert response.status_code == 409


def test_create_product_invalid_images(client, make_category):
    category = make_category()

    response = client.post('/products', json={
        'category_id': category.id,
        'product_name': 'Bad Images Product',
        'price': 1000,
        'sku': 'X-003',
        'images': ['ok.jpg', ''],
    })

    assert response.status_code == 400


# ---------------------------------------------------------------- PUT
def test_update_product_happy_path(client, make_product):
    product = make_product()

    response = client.put(f'/products/{product.id}', json={'price': 250000.00})

    assert response.status_code == 200
    assert response.get_json()['price'] == 250000.00


def test_update_product_not_found(client):
    response = client.put('/products/999', json={'price': 1000})

    assert response.status_code == 404


def test_update_product_negative_stock(client, make_product):
    product = make_product()

    response = client.put(f'/products/{product.id}', json={'stock_quantity': -1})

    assert response.status_code == 400


def test_update_product_slug_regenerated(client, make_product):
    product = make_product(name='Old Name')

    response = client.put(f'/products/{product.id}', json={'slug': 'New Custom Slug'})

    assert response.status_code == 200
    assert response.get_json()['slug'] == 'new-custom-slug'


# ---------------------------------------------------------------- DELETE
def test_delete_product_happy_path_is_soft_delete(client, db, make_product):
    product = make_product()

    response = client.delete(f'/products/{product.id}')

    assert response.status_code == 200
    # Row still exists in the DB (soft delete), just marked deleted.
    db.session.refresh(product)
    assert product.deleted_at is not None
    assert Product.query.count() == 1


def test_delete_product_not_found(client):
    response = client.delete('/products/999')

    assert response.status_code == 404


def test_delete_product_already_deleted(client, make_product):
    product = make_product()
    client.delete(f'/products/{product.id}')

    response = client.delete(f'/products/{product.id}')

    assert response.status_code == 409


def test_delete_product_blocked_by_active_order(client, db, make_product, make_user):
    product = make_product()
    user = make_user()

    order = Order(user_id=user.id, shipping_address='Jl. Merdeka No. 1', status='waiting', total_amount=199000.00)
    db.session.add(order)
    db.session.commit()

    db.session.execute(order_items.insert().values(
        order_id=order.id, product_id=product.id, quantity=1, unit_price=product.price,
    ))
    db.session.commit()

    response = client.delete(f'/products/{product.id}')

    assert response.status_code == 409
    assert Product.query.filter_by(id=product.id).first().deleted_at is None

"""
CRUD tests for the Category module: GET all, GET by id, POST, PUT, DELETE.
Each endpoint has a happy-path case and at least one error case.
"""
from app.models.category import Category


# ---------------------------------------------------------------- GET all
def test_list_categories_happy_path(client, make_category):
    """GET /categories returns 200 and every category as JSON."""
    make_category(name='Electronics')
    make_category(name='Apparel')

    response = client.get('/categories')

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 2
    assert {c['category_name'] for c in body} == {'Electronics', 'Apparel'}


def test_list_categories_empty(client):
    """GET /categories returns 200 and an empty list when there is no data."""
    response = client.get('/categories')

    assert response.status_code == 200
    assert response.get_json() == []


# ---------------------------------------------------------------- GET by id
def test_get_category_happy_path(client, make_category, make_product):
    """GET /categories/<id> returns 200, the category, and its products."""
    category = make_category()
    make_product(category_id=category.id, name='Wireless Mouse', sku='ELEC-MOUS-001')

    response = client.get(f'/categories/{category.id}')

    assert response.status_code == 200
    body = response.get_json()
    assert body['category_name'] == 'Electronics'
    assert len(body['products']) == 1
    assert body['products'][0]['sku'] == 'ELEC-MOUS-001'


def test_get_category_not_found(client, db):
    """GET /categories/<id> returns 404 with an error message for an unknown id."""
    response = client.get('/categories/999')

    assert response.status_code == 404
    assert 'error' in response.get_json()


# ---------------------------------------------------------------- POST
def test_create_category_happy_path(client, db):
    """POST /categories with a valid body returns 201 and the created category."""
    response = client.post('/categories', json={
        'category_name': 'Home Appliances',
        'description': 'Kitchen and household devices',
    })

    assert response.status_code == 201
    body = response.get_json()
    assert body['category_name'] == 'Home Appliances'
    assert body['id'] is not None
    assert Category.query.count() == 1


def test_create_category_missing_name(client, db):
    """POST /categories without category_name returns 400 with a meaningful message."""
    response = client.post('/categories', json={'description': 'No name provided'})

    assert response.status_code == 400
    assert 'category_name' in response.get_json()['error']
    assert Category.query.count() == 0


def test_create_category_duplicate_name(client, make_category):
    """POST /categories with a name that already exists returns 409."""
    make_category(name='Electronics')

    response = client.post('/categories', json={'category_name': 'Electronics'})

    assert response.status_code == 409
    assert 'error' in response.get_json()


def test_create_category_non_json_body(client):
    """POST /categories without a JSON body returns 400."""
    response = client.post('/categories', data='not-json')

    assert response.status_code == 400


# ---------------------------------------------------------------- PUT
def test_update_category_happy_path(client, make_category):
    """PUT /categories/<id> with valid data returns 200 and the updated category."""
    category = make_category(name='Electronics', description='Old description')

    response = client.put(f'/categories/{category.id}', json={
        'description': 'New description',
    })

    assert response.status_code == 200
    body = response.get_json()
    assert body['description'] == 'New description'
    assert body['category_name'] == 'Electronics'


def test_update_category_not_found(client):
    """PUT /categories/<id> for an unknown id returns 404."""
    response = client.put('/categories/999', json={'description': 'Anything'})

    assert response.status_code == 404


def test_update_category_duplicate_name(client, make_category):
    """PUT /categories/<id> renaming to an existing category's name returns 409."""
    make_category(name='Electronics')
    apparel = make_category(name='Apparel')

    response = client.put(f'/categories/{apparel.id}', json={'category_name': 'Electronics'})

    assert response.status_code == 409


def test_update_category_empty_name(client, make_category):
    """PUT /categories/<id> with an empty category_name returns 400."""
    category = make_category()

    response = client.put(f'/categories/{category.id}', json={'category_name': ''})

    assert response.status_code == 400


# ---------------------------------------------------------------- DELETE
def test_delete_category_happy_path(client, make_category):
    """DELETE /categories/<id> with no linked products returns 200 and removes it."""
    category = make_category()

    response = client.delete(f'/categories/{category.id}')

    assert response.status_code == 200
    assert Category.query.count() == 0


def test_delete_category_not_found(client):
    """DELETE /categories/<id> for an unknown id returns 404."""
    response = client.delete('/categories/999')

    assert response.status_code == 404


def test_delete_category_blocked_by_products(client, make_category, make_product):
    """DELETE /categories/<id> returns 409 when products still reference it."""
    category = make_category()
    make_product(category_id=category.id, name='Wireless Mouse', sku='ELEC-MOUS-002')

    response = client.delete(f'/categories/{category.id}')

    assert response.status_code == 409
    assert Category.query.count() == 1

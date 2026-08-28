import pytest
from flask_jwt_extended import create_access_token

from app import create_app, db as _db
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.utils import slugify
from config import TestConfig


@pytest.fixture
def app():
    """Creates a fresh Flask app + in-memory SQLite schema for every test."""
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client bound to the app fixture above."""
    return app.test_client()


@pytest.fixture
def db(app):
    """Convenience alias so tests can do `db.session` directly."""
    return _db


@pytest.fixture
def make_category(db):
    """Factory fixture: make_category(name='Electronics', description=None) -> Category."""
    def _make(name='Electronics', description=None):
        category = Category(category_name=name, description=description)
        db.session.add(category)
        db.session.commit()
        return category
    return _make


@pytest.fixture
def make_product(db, make_category):
    """
    Factory fixture: make_product(category_id=None, name='Wireless Mouse',
    sku='ELEC-MOUS-001', price=100000.00, stock=10, **extra) -> Product.

    Creates its own category automatically if category_id isn't supplied,
    and always derives a slug from `name` (slug is NOT NULL/unique at the
    model level, so every direct Product(...) construction needs one).
    """
    def _make(category_id=None, name='Wireless Mouse', sku='ELEC-MOUS-001',
              price=100000.00, stock=10, **extra):
        if category_id is None:
            category_id = make_category(name=f'Category-for-{sku}').id
        product = Product(
            category_id=category_id,
            product_name=name,
            slug=slugify(name) + f'-{sku.lower()}',
            price=price,
            stock_quantity=stock,
            sku=sku,
            images=extra.pop('images', []),
            **extra,
        )
        db.session.add(product)
        db.session.commit()
        return product
    return _make


@pytest.fixture
def make_user(db):
    """Factory fixture: make_user(email='budi@example.com', **extra) -> User."""
    def _make(email='budi@example.com', **extra):
        user = User(
            first_name=extra.pop('first_name', 'Budi'),
            last_name=extra.pop('last_name', 'Santoso'),
            email=email,
            password_hash=extra.pop('password_hash', 'x'),
            **extra,
        )
        db.session.add(user)
        db.session.commit()
        return user
    return _make


@pytest.fixture
def auth_header(app):
    """
    Factory fixture: auth_header(user_or_id) -> {'Authorization': 'Bearer <jwt>'}.

    Issues a real JWT access token for the given User (or raw user id)
    directly, bypassing POST /auth/login, so protected endpoints can be
    called in tests exactly as a real client would, via the Authorization
    header. Accepting a raw id (not just a User instance) lets tests
    build a token for an id that doesn't exist in the DB, e.g. to assert
    a 404 response from an endpoint that is otherwise correctly authorized.
    """
    def _make(user_or_id):
        identity = user_or_id.id if hasattr(user_or_id, 'id') else user_or_id
        with app.app_context():
            token = create_access_token(identity=str(identity))
        return {'Authorization': f'Bearer {token}'}
    return _make

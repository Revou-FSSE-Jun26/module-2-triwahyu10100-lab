"""
Marshmallow schemas for request body validation.

These schemas replace the hand-written "shape" validation that used to
live inline in each route (presence, type, numeric range, list
structure) — see PANDUAN_BELAJAR_CODING.md and
VALIDASI_DAN_STATUS_CODE.md for the full before/after comparison.

Two kinds of checks are deliberately kept OUTSIDE these schemas, still in
the route itself:

- Uniqueness checks that must exclude "the record currently being
  updated" (sku, category_name, username, email). marshmallow 4.x
  removed the old Schema.context mechanism that older versions used for
  this kind of thing (see the "Upgrading to 4.0" section of the
  marshmallow docs), and there is no built-in replacement that fits a
  one-off id exclusion cleanly. Keeping this in the route — right after
  schema.load() succeeds — is simpler and keeps the schema focused on
  pure data shape.
- Cross-table / stateful business rules that aren't about a single
  field's shape (e.g. "is there enough stock", "does this order allow
  item changes right now"). Those remain in the route/helper functions,
  unchanged from before.

Usage pattern in every route that uses a schema here:

    try:
        validated = SomeSchema().load(data)          # or load(data, partial=True) for PUT
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400

`err.messages` is a dict of `{field_name: [error, ...]}`, not a plain
string — this is a deliberate difference from the rest of this API's
hand-written validation (which always returns a single string under
`error`). See VALIDASI_DAN_STATUS_CODE.md for why this trade-off was
accepted rather than flattening it back into a string.
"""
from marshmallow import Schema, fields, validate, validates, ValidationError

from app.models.category import Category
from app.models.product import Product

__all__ = [
    'CategorySchema',
    'ProductSchema',
    'OrderItemSchema',
    'OrderCreateSchema',
    'UserRegisterSchema',
    'UserUpdateSchema',
    'LoginSchema',
    'ValidationError',
]


class CategorySchema(Schema):
    """Used for both POST /categories and PUT /categories/<id> (load(..., partial=True))."""

    class Meta:
        # Unknown keys in the body are silently dropped rather than
        # rejected — matches the old behavior, where routes only ever
        # read the specific fields they cared about from `data`.
        unknown = 'EXCLUDE'

    category_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, error='category_name cannot be empty'),
    )
    description = fields.Str(allow_none=True)


class ProductSchema(Schema):
    """
    Used for both POST /products and PUT /products/<id>
    (load(..., partial=True) for the latter).

    Deliberately does NOT validate `sku` uniqueness (needs to exclude the
    product being updated) or generate `slug` (that stays a
    product_routes.py concern, using slugify()/_resolve_unique_slug()
    same as before) — both remain in the route after schema.load().
    """

    class Meta:
        unknown = 'EXCLUDE'

    category_id = fields.Int(required=True)
    product_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, error='product_name cannot be empty'),
    )
    # slug is optional and, if provided, is re-slugified by the route —
    # this only guards against an explicitly empty string being sent.
    slug = fields.Str(allow_none=True, validate=validate.Length(min=1, error='slug cannot be empty'))
    description = fields.Str(allow_none=True)
    price = fields.Float(
        required=True,
        validate=validate.Range(min=0, error='price must be greater than or equal to 0'),
    )
    stock_quantity = fields.Int(
        validate=validate.Range(min=0, error='stock_quantity must be greater than or equal to 0'),
    )
    sku = fields.Str(required=True, validate=validate.Length(min=1, error='sku cannot be empty'))
    images = fields.List(
        fields.Str(validate=validate.Length(min=1, error='must be a non-empty string')),
        validate=validate.Length(max=10, error='images cannot contain more than 10 URLs'),
    )

    @validates('category_id')
    def validate_category_id_exists(self, value, data_key):
        """
        Referential check: only runs when category_id is present in the
        input (so it's naturally skipped on a partial PUT that doesn't
        touch category_id). No self-exclusion needed here — unlike sku
        uniqueness, a product's own category_id can never "conflict"
        with itself.
        """
        if Category.query.get(value) is None:
            raise ValidationError(f'Category with id {value} does not exist')


class OrderItemSchema(Schema):
    """One line item inside the `items` list of OrderCreateSchema."""

    class Meta:
        unknown = 'EXCLUDE'

    product_id = fields.Int(required=True)
    quantity = fields.Int(
        required=True,
        validate=validate.Range(min=1, error='quantity must be greater than 0'),
    )


class OrderCreateSchema(Schema):
    """
    Used for POST /orders. Only validates the request body's shape —
    duplicate product_id across lines, product existence, and stock
    availability are cross-table/stateful checks that stay in
    order_routes.py's _validate_and_resolve_items() helper, run right
    after this schema succeeds (see the comment there for why).
    """

    class Meta:
        unknown = 'EXCLUDE'

    shipping_address = fields.Str(
        required=True,
        validate=validate.Length(min=1, error='shipping_address cannot be empty'),
    )
    items = fields.List(
        fields.Nested(OrderItemSchema),
        required=True,
        validate=validate.Length(min=1, error='items must be a non-empty list'),
    )


class UserRegisterSchema(Schema):
    """Used for POST /users. Does not check email/username uniqueness — see module docstring."""

    class Meta:
        unknown = 'EXCLUDE'

    first_name = fields.Str(required=True, validate=validate.Length(min=1, error='first_name cannot be empty'))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, error='last_name cannot be empty'))
    email = fields.Email(required=True, error_messages={'invalid': 'email must be a valid email address'})
    password = fields.Str(required=True, validate=validate.Length(min=1, error='password cannot be empty'))
    username = fields.Str(allow_none=True)
    phone = fields.Str(allow_none=True)
    address = fields.Str(allow_none=True)


class UserUpdateSchema(Schema):
    """Used for PUT /users/<id> (load(..., partial=True)). Intentionally excludes email/password — see route docstring."""

    class Meta:
        unknown = 'EXCLUDE'

    username = fields.Str(allow_none=True)
    phone = fields.Str(allow_none=True)
    address = fields.Str(allow_none=True)


class LoginSchema(Schema):
    """Used for POST /auth/login."""

    class Meta:
        unknown = 'EXCLUDE'

    email = fields.Email(required=True, error_messages={'invalid': 'email must be a valid email address'})
    password = fields.Str(required=True, validate=validate.Length(min=1, error='password cannot be empty'))

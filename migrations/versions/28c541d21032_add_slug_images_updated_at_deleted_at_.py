"""add slug, images, updated_at, deleted_at to products; address, deleted_at to users

Revision ID: 28c541d21032
Revises: 513c63c14bff
Create Date: 2026-08-21 09:46:59.853791

"""
import re

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '28c541d21032'
down_revision = '513c63c14bff'
branch_labels = None
depends_on = None


def _slugify(text):
    text = text.strip().lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = re.sub(r'-{2,}', '-', text)
    return text.strip('-')


def upgrade():
    # NOTE: like the previous two migrations, `flask db migrate` also
    # picked up cosmetic diffs between the ORM models and the raw DDL in
    # schema.sql (indexes, CHECK constraints, FK ondelete clauses declared
    # outside the ORM). Those were removed by hand — this migration only
    # touches the genuinely new columns below.

    # --- products: slug, images, updated_at, deleted_at ---------------
    with op.batch_alter_table('products', schema=None) as batch_op:
        # Added nullable first so existing rows can be backfilled before
        # the NOT NULL / UNIQUE constraints are enforced.
        batch_op.add_column(sa.Column('slug', sa.String(length=180), nullable=True))
        batch_op.add_column(sa.Column('images', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))

    connection = op.get_bind()

    # Backfill slug from product_name for every existing row, guarding
    # against two products producing the same base slug.
    products = connection.execute(
        sa.text('SELECT product_id, product_name FROM products ORDER BY product_id')
    ).fetchall()

    seen_slugs = set()
    for product_id, product_name in products:
        base_slug = _slugify(product_name) or f'product-{product_id}'
        slug = base_slug
        suffix = 2
        while slug in seen_slugs:
            slug = f'{base_slug}-{suffix}'
            suffix += 1
        seen_slugs.add(slug)
        connection.execute(
            sa.text('UPDATE products SET slug = :slug WHERE product_id = :id'),
            {'slug': slug, 'id': product_id},
        )

    # Backfill images -> empty list, updated_at -> created_at, for every
    # existing row (new rows going forward get these from model defaults).
    connection.execute(sa.text("UPDATE products SET images = '[]' WHERE images IS NULL"))
    connection.execute(sa.text('UPDATE products SET updated_at = created_at WHERE updated_at IS NULL'))

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.alter_column('slug', existing_type=sa.String(length=180), nullable=False)
        batch_op.alter_column('images', existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column('updated_at', existing_type=sa.DateTime(), nullable=False)
        batch_op.create_unique_constraint('uq_products_slug', ['slug'])

    # --- users: address, deleted_at ------------------------------------
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('address', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('address')

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_constraint('uq_products_slug', type_='unique')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('images')
        batch_op.drop_column('slug')

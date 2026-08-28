"""
Shared helpers used across route modules: slug generation and generic
query-parameter parsing (pagination + sorting) for list endpoints.
"""
import re


def slugify(text):
    """
    Converts a string into a URL-safe, lowercase, hyphen-separated slug.

    Example: "Wireless Bluetooth Headphones!" -> "wireless-bluetooth-headphones"
    """
    text = text.strip().lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = re.sub(r'-{2,}', '-', text)
    return text.strip('-')


def parse_pagination(args, default_per_page=20, max_per_page=100):
    """
    Reads `page` and `per_page` from a request's query string (a
    werkzeug MultiDict, e.g. `request.args`).

    Returns (page, per_page, error). `error` is a string describing what
    went wrong, or None if both values are valid. Values are clamped to
    sane bounds instead of raising, except for outright non-integer input.
    """
    page_raw = args.get('page', '1')
    per_page_raw = args.get('per_page', str(default_per_page))

    try:
        page = int(page_raw)
    except ValueError:
        return None, None, 'page must be an integer'

    try:
        per_page = int(per_page_raw)
    except ValueError:
        return None, None, 'per_page must be an integer'

    if page < 1:
        return None, None, 'page must be greater than or equal to 1'
    if per_page < 1:
        return None, None, 'per_page must be greater than or equal to 1'

    per_page = min(per_page, max_per_page)
    return page, per_page, None


def parse_sort(args, allowed_fields, default='created_at', default_direction='desc'):
    """
    Reads a `sort` query parameter such as `sort=price` or `sort=-price`
    (leading `-` means descending). Returns (field, direction, error).

    `allowed_fields` is an iterable of column names that are safe to sort
    by (whitelisting avoids sorting by arbitrary/unmapped attributes).
    """
    sort_raw = args.get('sort', None)
    if not sort_raw:
        return default, default_direction, None

    direction = 'desc' if sort_raw.startswith('-') else 'asc'
    field = sort_raw.lstrip('-')

    if field not in allowed_fields:
        return None, None, f'sort must be one of: {", ".join(sorted(allowed_fields))} (optionally prefixed with -)'

    return field, direction, None


def paginate_query(query, page, per_page):
    """
    Applies offset/limit pagination to a SQLAlchemy query and returns a
    dict with the page of results plus pagination metadata.
    """
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page if per_page else 0

    return {
        'items': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_items': total,
            'total_pages': total_pages,
        },
    }

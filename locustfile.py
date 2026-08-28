"""
Locust load test for RevoShop.

Simulates a sequential user journey per virtual user:
  0. POST /users, POST /auth/login — register + log in (obtains a JWT
     access token used for every request below that requires auth)
  1. GET  /products               — browse the catalog
  2. GET  /products/<id>          — open one product from the list
  3. POST /orders                 — place an order for that product
  4. GET  /orders/<id>             — view the order just created

Each step depends on the previous one's response (the product id and the
new order id are only known at runtime), so the steps are modeled as a
SequentialTaskSet rather than independent @task methods — this guarantees
the four requests always fire in this exact order for every simulated user.

Usage
-----
Make sure the target API already has at least one user and one category
seeded (the task creates its own product per user to avoid depleting a
shared stock count across many virtual users).

Run locally against the dev server:
    locust -f locustfile.py --host http://127.0.0.1:5000

Run the full checkpoint scenario headless, ramping 50 -> 200 users:
    locust -f locustfile.py --host https://<your-deployed-api> \
        --users 200 --spawn-rate 10 --run-time 5m --headless

Note: `--users 200` is the target user count Locust ramps up to at
`--spawn-rate` users/second; start a smaller run first (e.g. --users 50)
to confirm the scenario works before ramping to 200.
"""
import random

from locust import HttpUser, SequentialTaskSet, between, task


class RevoShopJourney(SequentialTaskSet):
    def on_start(self):
        """
        Runs once per simulated user before the task sequence begins.
        Registers a throwaway user and product so every virtual user has
        its own data to order against, instead of contending over a
        single shared seed row. Also logs in immediately to obtain a JWT
        access token, since POST /orders (and friends) now require
        Authorization: Bearer <access_token>.
        """
        unique = random.randint(1, 10_000_000)
        password = 'LoadTest123'
        email = f'loadtest{unique}@example.com'

        register_resp = self.client.post('/users', json={
            'username': f'loadtest{unique}',
            'first_name': 'Load',
            'last_name': 'Test',
            'email': email,
            'password': password,
        })
        self.user_id = register_resp.json().get('id') if register_resp.status_code == 201 else None

        login_resp = self.client.post('/auth/login', json={'email': email, 'password': password})
        access_token = login_resp.json().get('access_token') if login_resp.status_code == 200 else None
        self.auth_headers = {'Authorization': f'Bearer {access_token}'} if access_token else {}

        category_resp = self.client.post('/categories', json={
            'category_name': f'LoadTestCategory{unique}',
        })
        category_id = category_resp.json().get('id') if category_resp.status_code == 201 else None

        product_resp = self.client.post('/products', json={
            'category_id': category_id,
            'product_name': f'Load Test Product {unique}',
            'price': 50000.00,
            'stock_quantity': 1000,
            'sku': f'LOAD-{unique}',
        })
        self.seed_product_id = product_resp.json().get('id') if product_resp.status_code == 201 else None

    @task
    def list_products(self):
        """Step 1 — GET /products: browse the catalog (public, no auth needed)."""
        response = self.client.get('/products')
        # GET /products replies with {"items": [...], "pagination": {...}}.
        items = response.json().get('items') if response.status_code == 200 else None
        if items:
            # Prefer a product from the live list; fall back to the seeded one.
            self.product_id = items[0]['id']
        else:
            self.product_id = self.seed_product_id

    @task
    def get_single_product(self):
        """Step 2 — GET /products/<id>: open a specific product."""
        if self.product_id is not None:
            self.client.get(f'/products/{self.product_id}')

    @task
    def create_order(self):
        """Step 3 — POST /orders: place a new order for that product (requires auth)."""
        self.order_id = None
        if self.user_id is None or self.product_id is None or not self.auth_headers:
            return

        response = self.client.post('/orders', json={
            'shipping_address': 'Jl. Locust Load Test No. 1',
            'items': [{'product_id': self.product_id, 'quantity': 1}],
        }, headers=self.auth_headers)
        if response.status_code == 201:
            self.order_id = response.json().get('id')

    @task
    def get_created_order(self):
        """Step 4 — GET /orders/<id>: view the order just created (requires auth)."""
        if self.order_id is not None:
            self.client.get(f'/orders/{self.order_id}', headers=self.auth_headers)


class RevoShopUser(HttpUser):
    tasks = [RevoShopJourney]
    # Each simulated user waits 1-3s between finishing one full journey
    # and starting the next, mimicking realistic browsing pauses.
    wait_time = between(1, 3)

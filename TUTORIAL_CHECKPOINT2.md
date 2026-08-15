# Tutorial Checkpoint 2 — Flask + SQLAlchemy + Migrasi (RevoShop)

Tutorial ini menjelaskan cara menjalankan, memverifikasi, dan mendemokan
aplikasi Flask Checkpoint 2 menggunakan **VS Code**, **DBeaver**, dan
**Postman**. Ditulis berdasarkan struktur proyek yang sudah dibuat di
repository ini.

---

## 0. Ringkasan struktur proyek

```
config.py                  -> konfigurasi Flask + SQLALCHEMY_DATABASE_URI
run.py                      -> entry point aplikasi
requirements.txt            -> daftar dependency
.env.example                -> template variabel environment (.env asli di-gitignore)
app/
  __init__.py               -> app factory (create_app), init db & migrate
  models/
    user.py                 -> model User (users table)
    category.py             -> model Category
    product.py               -> model Product
    order.py                -> model Order
    order_item.py            -> association table order_items (db.Table)
  routes/
    product_routes.py        -> GET /products, GET /products/<id> (hardcoded)
    user_routes.py            -> POST /users/register, GET /users/<id> (DB)
migrations/                  -> riwayat migrasi Flask-Migrate
1_checkpoint_revoshop_sql/    -> schema.sql & seed.sql dari Checkpoint 1
```

---

## 1. VS Code — Setup & Menjalankan Aplikasi

### 1.1 Buka proyek

1. Buka VS Code, `File > Open Folder...`, pilih folder repo ini.
2. Buka terminal terintegrasi: `Terminal > New Terminal` (pastikan shell = PowerShell).

### 1.2 Buat virtual environment

```powershell
python -m venv .venv
```

### 1.3 Aktifkan venv dan install dependency

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Jika PowerShell menolak menjalankan script aktivasi (`execution policy`),
jalankan sekali:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 1.4 Siapkan file `.env`

1. Copy `.env.example` menjadi `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Edit `.env`, sesuaikan `DATABASE_URL` dengan kredensial Postgres lokal kamu:
   ```
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/revoshop_db
   ```
   `.env` sudah masuk `.gitignore` sehingga tidak akan ter-commit.

### 1.5 Pastikan database `revoshop_db` sudah berisi schema Checkpoint 1

Kalau belum, jalankan `schema.sql` dan `seed.sql` dari folder
`1_checkpoint_revoshop_sql/` lewat DBeaver (lihat bagian 2) atau psql:
```powershell
psql -U postgres -h localhost -c "CREATE DATABASE revoshop_db;"
psql -U postgres -h localhost -d revoshop_db -f "1_checkpoint_revoshop_sql\schema.sql"
psql -U postgres -h localhost -d revoshop_db -f "1_checkpoint_revoshop_sql\seed.sql"
```

### 1.6 Jalankan migrasi (sekali saja, kalau belum pernah)

```powershell
$env:FLASK_APP = 'run.py'
flask db upgrade
```

Ini menerapkan seluruh riwayat migrasi di `migrations/versions/`:
- menambah kolom `username` ke `users`
- menambah kolom `role` ke `users` (default `'customer'`)

Kalau kamu ingin melihat proses migrate dari nol, baca bagian
[6. Reproduksi migrasi dari nol](#6-reproduksi-migrasi-dari-nol-opsional).

### 1.7 Jalankan aplikasi

```powershell
python run.py
```

Kalau berhasil, akan tampil:
```
* Running on http://127.0.0.1:5000
```

Biarkan terminal ini tetap berjalan selama testing di Postman.

---

## 2. DBeaver — Verifikasi Database

### 2.1 Koneksi ke `revoshop_db`

1. `Database > New Database Connection > PostgreSQL`.
2. Host `localhost`, Port `5432`, Database `revoshop_db`, user/password sesuai instalasi lokal.
3. Test Connection → Finish.

### 2.2 Verifikasi kolom `role` sudah ditambahkan tanpa merusak data lama

1. Klik kanan tabel `users` → **View/Edit Data** (atau double click).
2. Pastikan kolom `role` muncul, terisi `'customer'` di semua baris seed lama (Siti, Budi, Chelsea, dst).
3. Alternatif lewat SQL Editor:
   ```sql
   SELECT user_id, first_name, last_name, email, username, role
   FROM users
   ORDER BY user_id;
   ```
   Screenshot hasil ini sebagai bukti kolom `role` ada dan baris lama tidak hilang/null.

4. Untuk cek struktur kolom secara formal:
   ```sql
   SELECT column_name, data_type, is_nullable, column_default
   FROM information_schema.columns
   WHERE table_name = 'users'
   ORDER BY ordinal_position;
   ```

### 2.3 Verifikasi tabel `order_items` (many-to-many order <-> product)

1. Klik kanan tabel `order_items` → **View/Edit Data**, pastikan tabel ada dengan kolom `order_id`, `product_id`, `quantity`, `unit_price`.
2. Jalankan query pembuktian many-to-many (satu order, beberapa produk):
   ```sql
   SELECT o.order_id, o.status, p.product_name, oi.quantity, oi.unit_price
   FROM orders o
   JOIN order_items oi ON oi.order_id = o.order_id
   JOIN products p ON p.product_id = oi.product_id
   WHERE o.order_id = 2
   ORDER BY p.product_name;
   ```
   Order #2 pada data seed sudah berisi 3 produk berbeda (Mechanical Keyboard RGB, Atomic Habits, Cotton Crewneck T-Shirt) — screenshot hasil ini sebagai bukti relasi many-to-many berjalan.
3. Untuk melihat semua order yang punya lebih dari satu produk:
   ```sql
   SELECT o.order_id, array_agg(p.product_name) AS products
   FROM orders o
   JOIN order_items oi ON oi.order_id = o.order_id
   JOIN products p ON p.product_id = oi.product_id
   GROUP BY o.order_id
   HAVING count(*) > 1;
   ```

### 2.4 Verifikasi migrasi tercatat rapi

Cek tabel `alembic_version` (dibuat otomatis oleh Flask-Migrate):
```sql
SELECT * FROM alembic_version;
```
Isinya harus menunjukkan revision terakhir (`513c63c14bff` — migrasi role).

---

## 3. Postman — Testing Endpoint

Pastikan `python run.py` masih berjalan (server di `http://127.0.0.1:5000`).

### 3.1 GET /products (hardcoded, jsonify)

- Method: `GET`
- URL: `http://127.0.0.1:5000/products`
- Expected: status `200`, body array 5 produk (id, name, description, price, stock_quantity, sku).
- Screenshot response body ini.

### 3.2 GET /products/<id>

- Method: `GET`
- URL: `http://127.0.0.1:5000/products/2`
- Expected: status `200`, body satu objek produk dengan `id: 2`.
- Coba juga id yang tidak ada, misal `http://127.0.0.1:5000/products/999` → expected `404` dengan body `{"error": "Product with id 999 not found"}`. Screenshot kedua kasus ini (found & not-found).

### 3.3 POST /users/register (buat user baru ke database)

- Method: `POST`
- URL: `http://127.0.0.1:5000/users/register`
- Headers: `Content-Type: application/json`
- Body (raw JSON):
  ```json
  {
    "username": "ratna01",
    "first_name": "Ratna",
    "last_name": "Dewi",
    "email": "ratna.dewi@example.com",
    "phone": "+62-817-0000-1111",
    "password": "SuperSecret123"
  }
  ```
- Expected: status `201`, body berisi user baru termasuk `id`, `role: "customer"`, `created_at`. `password_hash` tidak dikembalikan di response (hanya field aman).
- Coba kirim lagi dengan email yang sama → expected `409 Conflict` (`"A user with this email already exists"`). Screenshot ini sebagai bukti validasi bekerja.

### 3.4 GET /users/<id> (retrieve dari database)

- Method: `GET`
- URL: `http://127.0.0.1:5000/users/1` (atau id user hasil register di atas)
- Expected: status `200`, body data user lengkap termasuk `role`.
- Coba juga id yang tidak ada, misal `http://127.0.0.1:5000/users/9999` → expected `404` (`"User with id 9999 not found"`). Screenshot kedua kasus ini (found & not-found), sesuai requirement rubrik.

---

## 4. Catatan desain penting

- **Kolom `username` vs `first_name`/`last_name`**: schema Checkpoint 1
  (`schema.sql`) hanya punya `first_name`/`last_name`, bukan `username`.
  Karena spesifikasi Checkpoint 2 minta `username`, kolom ini ditambahkan
  lewat migrasi baru (bukan menghapus `first_name`/`last_name`) supaya data
  seed lama tetap valid.
- **`role` ditambahkan lewat migrasi terpisah** dengan `server_default='customer'`,
  jadi baris lama otomatis terisi `'customer'`, tidak `NULL`.
- **Migrasi baseline** (`69cd99b04162`) hanya berisi penambahan kolom
  `username` — perbedaan index/constraint kosmetik hasil auto-generate
  (karena constraint dari `schema.sql` dibuat manual via SQL, bukan lewat
  ORM) sudah dihapus manual dari file migrasi agar tidak menghapus
  index/constraint yang sudah benar di database.
- **`order_items`** didefinisikan sebagai `db.Table()` (association table),
  bukan model class, sesuai requirement checkpoint, lengkap dengan kolom
  `quantity` dan `unit_price` sebagai snapshot harga saat order dibuat.

---

## 5. Menjalankan test cepat lewat terminal (opsional, tanpa Postman)

```powershell
# GET semua produk
Invoke-RestMethod -Uri http://127.0.0.1:5000/products -Method GET

# GET satu produk
Invoke-RestMethod -Uri http://127.0.0.1:5000/products/2 -Method GET

# Register user baru
$body = @{
    username='ratna01'; first_name='Ratna'; last_name='Dewi'
    email='ratna.dewi@example.com'; phone='+62-817-0000-1111'
    password='SuperSecret123'
} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:5000/users/register -Method POST -Body $body -ContentType 'application/json'

# Retrieve user
Invoke-RestMethod -Uri http://127.0.0.1:5000/users/1 -Method GET
```

---

## 6. Reproduksi migrasi dari nol (opsional)

Kalau ingin melihat sendiri proses `flask db migrate` dari awal (misalnya di
database kosong baru):

```powershell
$env:FLASK_APP = 'run.py'
flask db init                       # sekali saja, bikin folder migrations/
flask db migrate -m "pesan migrasi"  # generate file migrasi baru
# review dulu file yang dihasilkan di migrations/versions/ sebelum lanjut
flask db upgrade                     # terapkan migrasi ke database
```

Penting: kalau tabel sudah ada duluan lewat `schema.sql` (bukan lewat
Alembic), `flask db migrate` akan otomatis mendeteksi perbedaan kosmetik
(index, check constraint, foreign key ondelete) yang sebenarnya bukan
perubahan nyata — sebelum menjalankan `flask db upgrade`, selalu buka dan
baca file migrasi hasil auto-generate, dan hapus bagian yang tidak
seharusnya diubah.

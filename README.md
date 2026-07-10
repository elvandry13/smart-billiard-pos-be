# Smart Billiard POS — Backend API

Backend API untuk sistem Point of Sale (POS) biliar berbasis **Django REST Framework**. Proyek ini menyediakan REST API untuk mengelola meja biliar, sesi permainan, paket jam, pembayaran, struk PDF, shift karyawan, dashboard analitik, dan log audit — dengan arsitektur multi-tenant (Tenant → Outlet).

## Fitur

| Modul | Deskripsi |
|-------|-----------|
| **Users** | Manajemen user, role, permission, tenant, dan outlet. Autentikasi JWT (login/logout/refresh/ganti password). |
| **Tables** | CRUD tipe meja dan meja biliar. Setiap meja terikat ke outlet. |
| **Sessions** | Sesi permainan biliar — start, pause, resume, stop. Kalkulasi biaya berdasarkan pricing rules yang aktif. |
| **Packages** | Paket jam main (misal: 3 jam Rp 50.000). Bisa digunakan sebagai alternatif tarif normal. |
| **Payments** | Pencatatan pembayaran sesi (tunai, QRIS, dll). Termasuk additional fees (biaya tambahan) dan diskon. |
| **Receipts** | Generate struk PDF dengan ReportLab. Struk bisa di-download atau dikirim via API. |
| **Shifts** | Manajemen shift karyawan — open shift, close shift, catat kas awal/akhir. |
| **Dashboard** | Endpoint ringkasan untuk dashboard: total sesi aktif, pendapatan hari ini, shift aktif, dll. |
| **Audit Logs** | Pencatatan otomatis aktivitas penting (create/update/delete) di seluruh sistem. |

## Tech Stack

- **Python** 3.x
- **Django** 4.2
- **Django REST Framework** 3.14
- **Simple JWT** — JSON Web Token authentication
- **drf-spectacular** — OpenAPI 3 schema & dokumentasi (Swagger UI / ReDoc)
- **django-cors-headers** — CORS handling
- **django-filter** — Filtering & searching
- **ReportLab** — PDF generation untuk struk
- **psycopg2-binary** — PostgreSQL adapter
- **python-decouple** — Environment variable management

## Struktur Proyek

```
smart-billiard-pos-be/
├── core/               # Django project settings & entry point
│   ├── settings/       # base.py, development.py, production.py
│   ├── urls.py         # Root URL configuration
│   └── wsgi.py / asgi.py
├── users/              # User, Role, Permission, Tenant, Outlet
├── tables/             # TableType & Table CRUD
├── sessions/           # Sesi permainan biliar
├── packages/           # Paket jam main
├── payments/           # Pembayaran & additional fees
├── receipts/           # Generate struk PDF
├── shifts/             # Shift karyawan
├── dashboard/          # Endpoint ringkasan dashboard
├── audit_logs/         # Log audit otomatis
├── schema.yaml         # OpenAPI 3 schema (drf-spectacular output)
├── requirements.txt    # Dependency Python
├── manage.py           # Django CLI entry point
├── .env.example        # Template environment variables
└── README.md
```

## Prasyarat

- Python 3.10+
- PostgreSQL (disarankan untuk production) atau SQLite (untuk development)
- `pip` dan `virtualenv`

## Instalasi & Setup

### 1. Clone Repository

```bash
git clone https://github.com/elvandry13/smart-billiard-pos-be.git
cd smart-billiard-pos-be
```

### 2. Buat Virtual Environment & Install Dependencies

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Konfigurasi Environment Variables

Salin `.env.example` ke `.env` dan sesuaikan nilainya:

```bash
cp .env.example .env
```

Buka `.env` dan isi variabel berikut:

| Variabel | Deskripsi | Default |
|----------|-----------|---------|
| `DJANGO_SECRET_KEY` | Secret key Django (**wajib diubah**) | — |
| `DJANGO_ENV` | `development` atau `production` | `development` |
| `DJANGO_DEBUG` | Debug mode (`True` / `False`) | `True` |
| `DATABASE_URL` | URL database (PostgreSQL atau SQLite) | `sqlite:///db.sqlite3` |
| `DJANGO_ALLOWED_HOSTS` | Host yang diizinkan (koma-pisah) | `localhost,127.0.0.1` |
| `SUPER_ADMIN_USERNAME` | Username seed superadmin | `superadmin` |
| `SUPER_ADMIN_EMAIL` | Email seed superadmin | — |
| `SUPER_ADMIN_PASSWORD` | Password seed superadmin (**wajib diubah**) | — |

**Contoh PostgreSQL:**
```
DATABASE_URL=postgres://user:password@localhost:5432/smart_billiard_db
```

### 4. Jalankan Migrasi Database

```bash
python manage.py migrate
```

### 5. Seed Super Admin (Opsional)

Membuat user super admin awal:

```bash
python manage.py seed_superadmin
```

Gunakan kredensial yang sudah diisi di `.env` (`SUPER_ADMIN_USERNAME`, `SUPER_ADMIN_PASSWORD`).

### 5b. Seed Minimal Phase 1 Frontend E2E (Opsional)

Membuat data minimal untuk validasi frontend Phase 1 end-to-end:

- 1 tenant aktif.
- 1 outlet aktif.
- 4 user aktif: `super_admin`, `owner`, `admin`, `officer`.

```bash
python manage.py seed_phase1
```

Command ini membaca password dari environment variable lokal:

- `PHASE1_SUPER_ADMIN_PASSWORD`
- `PHASE1_OWNER_PASSWORD`
- `PHASE1_ADMIN_PASSWORD`
- `PHASE1_OFFICER_PASSWORD`

Username, email, tenant, dan outlet bisa dioverride melalui variable `PHASE1_*` di `.env.example`.

> **Keamanan:** credential test nyata tidak boleh disimpan di repository. Simpan di `.env` lokal yang tidak di-commit, dokumentasi internal terpisah, atau password manager.

### 6. Jalankan Server Development

```bash
python manage.py runserver
```

Server berjalan di **http://localhost:8000**

## Dokumentasi API

Setelah server berjalan, dokumentasi interaktif tersedia di:

- **Swagger UI**: [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)
- **ReDoc**: [http://localhost:8000/api/redoc/](http://localhost:8000/api/redoc/)
- **OpenAPI Schema (JSON/YAML)**: [http://localhost:8000/api/schema/](http://localhost:8000/api/schema/)

Dokumentasi digenerate otomatis oleh **drf-spectacular** sesuai standar OpenAPI 3.0.

## Autentikasi

API menggunakan **JWT (JSON Web Token)** untuk autentikasi.

| Endpoint | Method | Deskripsi |
|----------|--------|-----------|
| `/api/auth/login/` | POST | Login — mendapatkan access & refresh token |
| `/api/auth/refresh/` | POST | Refresh access token |
| `/api/auth/logout/` | POST | Logout — blacklist refresh token |
| `/api/auth/password/change/` | POST/PUT | Ganti password user yang sedang login |
| `/api/profile/` | GET/PUT/PATCH | Lihat & edit profil sendiri |

**Header Autentikasi:**
```
Authorization: Bearer <access_token>
```

## Ringkasan Modul

### Users (`/api/`)
- **Outlets** — CRUD outlet (hanya Super Admin)
- **Users** — CRUD user per outlet
- **Roles & Permissions** — Role-based access control
- **Profile** — Profil user login
- **Auth** — Login, logout, refresh, change password

### Tables (`/api/table-types/`, `/api/tables/`)
- **Table Types** — Kategori meja (regular, VIP, dll)
- **Tables** — Meja biliar individual

### Pricing Rules (`/api/pricing-rules/`)
- Aturan harga per jam berdasarkan tipe meja, hari (weekday/weekend/specific_day), dan jam tertentu

### Additional Fees (`/api/additional-fees/`)
- Biaya tambahan: fixed (nominal tetap) atau percentage (persentase dari total)

### Sessions (`/api/sessions/`)
- Sesi permainan: start, pause, resume, stop
- Auto-kalkulasi biaya berdasarkan durasi × pricing rule

### Packages (`/api/packages/`)
- Paket jam main dengan harga flat

### Payments (`/api/payments/`)
- Pembayaran sesi (cash, QRIS, transfer, dll)
- Support diskon dan biaya tambahan
- Ringkasan pendapatan

### Receipts (`/api/receipts/`)
- Generate PDF struk pembayaran via ReportLab
- Endpoint untuk download PDF

### Shifts (`/api/shifts/`)
- Buka/tutup shift karyawan
- Catat kas awal dan kas akhir

### Dashboard (`/api/dashboard/`)
- Sesi aktif hari ini
- Pendapatan hari ini
- Shift yang sedang berjalan
- Ringkasan cepat untuk tampilan dashboard

### Audit Logs (`/api/audit-logs/`)
- Log otomatis semua aksi create/update/delete
- Read-only, bisa difilter by user, action, model, timestamp

## Menjalankan Tes

```bash
# Semua tes
python manage.py test

# Tes modul spesifik
python manage.py test users
python manage.py test sessions
python manage.py test payments
# ... dst
```

## Tips Development

- **Environment**: Gunakan `DJANGO_ENV=development` — settings development otomatis dari `core/settings/development.py` (DEBUG=True, SQLite, CORS terbuka).
- **Production**: Atur `DJANGO_ENV=production` dan `DATABASE_URL` ke PostgreSQL. Jangan lupa `DJANGO_DEBUG=False`.
- **Super Admin**: Seed awal via `seed_superadmin` akan membuat user super admin. Untuk data minimal tenant/outlet + 4 role frontend Phase 1, gunakan `seed_phase1`.
- **Media Files**: File PDF struk disimpan di `MEDIA_ROOT`. Di development, file dilayani langsung oleh Django.
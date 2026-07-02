# Implementation Plan — Fase 3: Package Management

[Overview]
Menambahkan app `packages` baru untuk menyediakan CRUD Package Management yang memungkinkan Admin mengelola paket bermain (per_minute, fixed_duration, open_loss, happy_hour) per outlet, lengkap dengan validasi business rule, testing, dan auto-scoping outlet.

Fase 3 menambahkan entitas `Package` ke sistem Smart Billiard POS. Package adalah fitur inti yang memungkinkan outlet menawarkan berbagai paket bermain dengan aturan harga berbeda. Model ini akan menjadi fondasi untuk Fase 5 (Play Session) dimana sesi bermain dapat dikaitkan dengan Package tertentu. Implementasi mengikuti pola yang sudah mapan di app `tables` — menggunakan `OutletScopedViewSet`, `IsAdminOrSuperAdmin` permission, `DecimalField` untuk harga, dan `django_filters` untuk filtering. App baru `packages` dibuat terpisah sesuai keputusan desain untuk menjaga separation of concerns; ke depannya app ini bisa menampung business logic terkait package (seperti resolusi harga package vs dynamic pricing).

[Types]
Tidak ada perubahan type system pada app yang sudah ada. Satu model baru ditambahkan di app `packages`.

### Model: `Package` (packages/models.py)

| Field | Type | Constraints | Keterangan |
|---|---|---|---|
| `id` | AutoField (PK) | auto | Primary key |
| `outlet` | FK → Outlet | CASCADE, related_name='packages' | Outlet pemilik package |
| `name` | CharField(100) | required | Nama package (mis. "Paket 3 Jam") |
| `type` | CharField(20) | choices=PackageType | Tipe package |
| `duration_minutes` | PositiveIntegerField | nullable, blank=True | Durasi dalam menit (untuk fixed_duration, happy_hour) |
| `fixed_price` | DecimalField(10,2) | nullable, blank=True | Harga tetap (untuk fixed_duration, happy_hour) |
| `price_per_minute` | DecimalField(10,2) | nullable, blank=True | Harga per menit (untuk per_minute, open_loss) |
| `valid_day_type` | CharField(20) | choices=DayType, default='all' | Hari berlaku: all/weekday/weekend/specific_day |
| `specific_date` | DateField | nullable, blank=True | Tanggal spesifik (jika valid_day_type=specific_day) |
| `valid_start_time` | TimeField | nullable, blank=True | Jam mulai berlaku |
| `valid_end_time` | TimeField | nullable, blank=True | Jam akhir berlaku |
| `is_active` | BooleanField | default=True | Status aktif/nonaktif |
| `created_at` | DateTimeField | auto_now_add | Timestamp pembuatan |
| `updated_at` | DateTimeField | auto_now | Timestamp update terakhir |

### Enum: `PackageType` (inner class di model `Package`)

| Nilai | Label | Deskripsi |
|---|---|---|
| `per_minute` | Per Minute | Tarif per menit, durasi bebas |
| `fixed_duration` | Fixed Duration | Durasi tetap + harga tetap |
| `open_loss` | Open Loss | Main sampai kalah, tarif per menit |
| `happy_hour` | Happy Hour | Paket durasi + harga spesial di jam tertentu |

### Enum: `DayType` (inner class di model `Package`)

| Nilai | Label |
|---|---|
| `all` | All Days |
| `weekday` | Weekday |
| `weekend` | Weekend |
| `specific_day` | Specific Day |

### Meta Constraints:
- `unique_together = ['outlet', 'name']` — nama package unik per outlet
- `ordering = ['outlet', 'name']`

### Validation Rules (model `clean()`):
1. `fixed_duration` + `happy_hour`: wajib isi `duration_minutes` DAN `fixed_price`
2. `per_minute`: wajib isi `price_per_minute`, `duration_minutes` DAN `fixed_price` boleh null
3. `open_loss`: `duration_minutes` harus null (karena durasi tidak tetap), `fixed_price` harus null, `price_per_minute` opsional (kalau null → pakai PricingRule)
4. `duration_minutes` > 0 jika diisi
5. `fixed_price` > 0 jika diisi
6. `price_per_minute` > 0 jika diisi
7. `valid_day_type == 'specific_day'` → `specific_date` wajib
8. `valid_day_type != 'specific_day'` → `specific_date` harus null
9. `valid_start_time` < `valid_end_time` jika keduanya diisi

### Serializer Type: `PackageSerializer` (packages/serializers.py)
- ModelSerializer untuk Package
- Fields: `id`, `outlet`, `name`, `type`, `duration_minutes`, `fixed_price`, `price_per_minute`, `valid_day_type`, `specific_date`, `valid_start_time`, `valid_end_time`, `is_active`, `created_at`, `updated_at`
- Read-only: `created_at`, `updated_at`
- `validate()` method menduplikasi logika `clean()` model untuk DRF-level validation

[Files]
Semua perubahan berada di app baru `packages/` dengan 1 file konfigurasi yang dimodifikasi.

### New Files:
- **`packages/__init__.py`** — package init, kosong
- **`packages/apps.py`** — Django AppConfig dengan nama `PackagesConfig`, label `packages`
- **`packages/models.py`** — Model `Package` dengan enum `PackageType`, `DayType`, dan validasi `clean()`
- **`packages/serializers.py`** — `PackageSerializer` dengan validasi field-level
- **`packages/views.py`** — `PackageViewSet` extends `OutletScopedViewSet` (base class yang sudah didefinisikan di `tables/views.py` — perlu dipindahkan ke file terpisah atau diimport dari `tables`)
- **`packages/urls.py`** — Router DRF dengan `register(r'packages', PackageViewSet, basename='package')`
- **`packages/admin.py`** — Admin registration untuk model Package
- **`packages/tests.py`** — Test cases: CRUD Package, validasi tipe package, scoping outlet, unique constraint
- **`packages/migrations/__init__.py`** — Migrations init, kosong
- **`packages/migrations/0001_initial.py`** — Auto-generated migration (via `makemigrations`)

### Modified Files:
- **`core/settings/base.py`** — Tambahkan `'packages'` ke `INSTALLED_APPS`
- **`core/urls.py`** — Tambahkan `path('api/', include('packages.urls'))` ke `urlpatterns`

### Dependency Note:
- `PackageViewSet` meng-extend `OutletScopedViewSet` yang saat ini didefinisikan di `tables/views.py`. Karena base class ini akan digunakan oleh `packages/views.py`, maka `OutletScopedViewSet` harus dipindahkan ke lokasi yang dapat di-share (misalnya `core/views.py` atau `tables/views.py` tetap dengan import dari `packages`). **Rekomendasi: pindahkan `OutletScopedViewSet` ke `core/views.py`** agar tidak terjadi circular dependency dan dapat digunakan oleh app `packages` maupun `tables`.

[Functions]
Tidak ada fungsi standalone baru. Semua logic dienkapsulasi dalam class Model, Serializer, dan ViewSet.

### New Classes/Methods:

#### `OutletScopedViewSet` — dipindahkan dari `tables/views.py` ke `core/views.py`
- **Purpose**: Base ViewSet yang dapat di-share antar app untuk auto-scoping outlet
- **Perubahan**: Pindahkan class definition dari `tables/views.py` ke `core/views.py`
- **Impact**: `tables/views.py` harus import dari `core.views`; `packages/views.py` juga import dari `core.views`

#### `PackageViewSet(OutletScopedViewSet)` — packages/views.py
- **queryset**: `Package.objects.select_related('outlet').all()`
- **serializer_class**: `PackageSerializer`
- **filter_backends**: `[DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]`
- **filterset_fields**: `['type', 'valid_day_type', 'is_active']`
- **search_fields**: `['name']`
- **ordering_fields**: `['name', 'created_at', 'type']`

#### `PackageSerializer.validate()` — packages/serializers.py
- Validasi sesuai aturan PackageType:
  - `fixed_duration` + `happy_hour` → `duration_minutes` & `fixed_price` required
  - `per_minute` → `price_per_minute` required
  - `open_loss` → `duration_minutes` & `fixed_price` must be null
  - Numeric fields > 0
  - `specific_date` logic sesuai `valid_day_type`

#### `Package.clean()` — packages/models.py
- Full model-level validation (duplikasi logika serializer untuk double safety)

### Modified Functions:
- `tables/views.py`: Hapus definisi `OutletScopedViewSet`, ganti dengan import dari `core.views`

[Classes]
Satu class model baru, satu serializer baru, satu ViewSet baru, dan pemindahan satu base ViewSet.

### New Classes:
- **`Package`** (packages/models.py) — Model untuk package bermain, dengan inner enum `PackageType` dan `DayType`
- **`PackageSerializer`** (packages/serializers.py) — DRF ModelSerializer untuk Package
- **`PackageViewSet`** (packages/views.py) — DRF ModelViewSet untuk CRUD Package, scoped ke outlet
- **`PackagesConfig`** (packages/apps.py) — Django AppConfig

### Modified Classes:
- **`OutletScopedViewSet`** — Dipindahkan dari `tables/views.py` ke `core/views.py` (lokasi baru)
  - Semua import di `tables/views.py` diperbarui ke `from core.views import OutletScopedViewSet`

[Dependencies]
Tidak ada dependency eksternal baru.

### Existing Dependencies yang Digunakan:
- `Django==4.2.30` — model, ORM, validasi
- `djangorestframework>=3.14` — ViewSet, Serializer, Router
- `django-filter` — sudah tersedia (digunakan di `tables/views.py` via `DjangoFilterBackend`)
- Tidak ada penambahan package baru di `requirements.txt`

### Integration Points:
- `core/settings/base.py` → `INSTALLED_APPS` ditambah `'packages'`
- `core/urls.py` → `urlpatterns` ditambah `path('api/', include('packages.urls'))`
- `core/views.py` → file baru untuk `OutletScopedViewSet` (shared base class)

[Testing]
Test cases untuk CRUD Package, validasi tipe package, scoping outlet, dan unique constraint.

### Test File: `packages/tests.py`

#### Test Class: `PackageAPITests(TestCase)`
1. **test_list_packages_as_admin** — Admin hanya lihat package di outlet-nya
2. **test_create_fixed_duration_package** — Buat package fixed_duration dengan duration_minutes & fixed_price
3. **test_create_per_minute_package** — Buat package per_minute dengan price_per_minute
4. **test_create_open_loss_package** — Buat package open_loss (duration_minutes & fixed_price harus null)
5. **test_create_happy_hour_package** — Buat package happy_hour dengan durasi & fixed_price
6. **test_fixed_duration_requires_duration_and_price** — Validasi: fixed_duration tanpa duration_minutes → 400
7. **test_per_minute_requires_price_per_minute** — Validasi: per_minute tanpa price_per_minute → 400
8. **test_open_loss_rejects_fixed_price** — Validasi: open_loss dengan fixed_price → 400
9. **test_specific_day_requires_date** — Validasi: specific_day tanpa specific_date → 400
10. **test_duplicate_name_rejected** — Unique constraint outlet+name → 400
11. **test_super_admin_sees_all** — Super Admin lihat package semua outlet
12. **test_officer_cannot_create** — Officer tidak bisa CRUD package → 403
13. **test_update_package** — Admin update package di outlet-nya → 200
14. **test_delete_package** — Admin delete package di outlet-nya → 204
15. **test_create_package_with_invalid_duration** — duration_minutes negatif → 400

### Expected Test Run:
```bash
python manage.py test packages.tests.PackageAPITests
```
Semua 15 test case harus PASS.

[Implementation Order]
Urutan implementasi yang meminimalkan konflik dan memastikan integrasi yang sukses.

1. **Pindahkan `OutletScopedViewSet` dari `tables/views.py` ke `core/views.py`**
   - Buat file `core/views.py` dengan definisi `OutletScopedViewSet`
   - Update import di `tables/views.py` menjadi `from core.views import OutletScopedViewSet`
   - Verifikasi: `python manage.py check` — tidak ada error

2. **Buat app `packages` dan semua file dasarnya**
   - `packages/__init__.py`
   - `packages/apps.py`
   - `packages/admin.py`

3. **Implementasi model `Package` di `packages/models.py`**
   - Definisikan model, enum, `clean()`, dan `Meta`
   - Verifikasi: `python manage.py makemigrations packages` → sukses

4. **Jalankan migrasi**
   - `python manage.py migrate packages`
   - Verifikasi: tabel `packages_package` terbuat

5. **Implementasi serializer `PackageSerializer` di `packages/serializers.py`**
   - Definisikan field dan `validate()` dengan semua aturan validasi

6. **Implementasi ViewSet `PackageViewSet` di `packages/views.py`**
   - Extends `OutletScopedViewSet`, set queryset, serializer, filter backends

7. **Implementasi URLs di `packages/urls.py`**
   - Router DRF dengan endpoint `packages`

8. **Update konfigurasi project**
   - Tambahkan `'packages'` ke `INSTALLED_APPS` di `core/settings/base.py`
   - Tambahkan `path('api/', include('packages.urls'))` ke `core/urls.py`
   - Verifikasi: `python manage.py check` + `python manage.py show_urls` (atau cek Swagger)

9. **Implementasi test cases di `packages/tests.py`**
   - Tulis 15 test case sesuai [Testing] section
   - Verifikasi: `python manage.py test packages.tests.PackageAPITests` — semuanya PASS

10. **Verifikasi integrasi end-to-end**
    - Jalankan semua test: `python manage.py test` — tidak ada regression
    - Cek Swagger docs: endpoint `/api/packages/` muncul
    - Manual smoke test via API client (optional)
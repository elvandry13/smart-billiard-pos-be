# Implementation Plan — Fase 5: Play Session

[Overview]
Membangun modul Play Session yang menangani siklus hidup sesi bermain billiard: start session, real-time cost tracking, transfer table, end session (dengan auto-kalkulasi biaya + AdditionalFee), dan cancel session — seluruhnya terhubung ke Shift aktif officer.

Fase 5 adalah inti operasional dari sistem POS billiard. Modul ini menghubungkan seluruh entitas yang sudah dibangun di fase sebelumnya: Table (fase 2), PricingRule + AdditionalFee (fase 2), Package (fase 3), dan Shift (fase 4). PlaySession menggunakan pola arsitektur yang konsisten dengan codebase existing: model Django dengan `validate_invariants()` static method, serializer DRF dengan `validate()`, dan ViewSet dengan permission scoping berbasis outlet. Business logic utama — kalkulasi biaya, pemilihan pricing rule, transfer table, dan auto-apply AdditionalFee — dienkapsulasi di service layer (`sessions/services.py`) agar reusable dan testable secara terpisah.

[Types]
Mendefinisikan dua model baru (PlaySession, SessionTableLog), beberapa enum choices, dan service functions untuk kalkulasi biaya.

### PlaySession Model
- **Fields:**
  - `id` (BigAutoField, PK)
  - `outlet` (FK → Outlet, PROTECT, related_name='play_sessions')
  - `shift` (FK → Shift, PROTECT, related_name='play_sessions') — shift aktif officer saat sesi dibuka
  - `customer_name` (CharField, max_length=100)
  - `customer_phone` (CharField, max_length=20, blank=True, default='')
  - `initial_table` (FK → Table, PROTECT, related_name='play_sessions') — meja pertama saat sesi dibuka
  - `package` (FK → Package, SET_NULL, null=True, blank=True, related_name='play_sessions') — nullable untuk open-play
  - `status` (CharField, max_length=20, choices: running/completed/cancelled, default=running)
  - `started_at` (DateTimeField, auto_now_add=True) — waktu sesi dimulai
  - `ended_at` (DateTimeField, null=True, blank=True) — diisi saat completed/cancelled
  - `officer_start` (FK → User, PROTECT, related_name='sessions_started') — officer yang membuka sesi
  - `officer_end` (FK → User, SET_NULL, null=True, blank=True, related_name='sessions_ended') — officer yang menutup/membatalkan
  - `subtotal` (DecimalField, max_digits=12, decimal_places=2, null=True, blank=True) — total biaya permainan (sum semua SessionTableLog.amount, atau fixed_price package)
  - `additional_fee_total` (DecimalField, max_digits=12, decimal_places=2, null=True, blank=True) — total AdditionalFee
  - `total_amount` (DecimalField, max_digits=12, decimal_places=2, null=True, blank=True) — subtotal + additional_fee_total
  - `cancel_reason` (TextField, blank=True, default='') — wajib diisi saat cancel
  - `created_at` (DateTimeField, auto_now_add=True)
- **Status Enum (TextChoices):**
  - `RUNNING = 'running', 'Running'`
  - `COMPLETED = 'completed', 'Completed'`
  - `CANCELLED = 'cancelled', 'Cancelled'`
- **Validation Rules (validate_invariants):**
  - `package.outlet_id` harus sama dengan `outlet_id` (jika package tidak null)
  - Saat create: `initial_table.status` harus `available`, dan `initial_table.outlet_id` == `outlet_id`
  - Saat start: officer harus memiliki `Shift` open di outlet yang sama (divalidasi via `shift` field)
  - Status `completed`: `ended_at` harus terisi, `subtotal` + `additional_fee_total` + `total_amount` harus terisi
  - Status `cancelled`: `ended_at` harus terisi, `cancel_reason` wajib diisi, `subtotal`/`additional_fee_total`/`total_amount` harus null (tidak dihitung sebagai revenue)
  - Status hanya bisa transisi: running → completed, running → cancelled (completed tidak bisa menjadi apa pun)
- **Meta:**
  - `ordering = ['-started_at']`

### SessionTableLog Model
- **Fields:**
  - `id` (BigAutoField, PK)
  - `session` (FK → PlaySession, CASCADE, related_name='table_logs')
  - `table` (FK → Table, PROTECT, related_name='session_logs')
  - `rate_source_type` (CharField, max_length=20, choices: pricing_rule/package_rate)
  - `rate_source_snapshot` (JSONField) — menyimpan salinan lengkap tarif yang berlaku saat segmen berjalan:
    ```json
    {
      "source": "pricing_rule" | "package_rate",
      "pricing_rule_id": 123,          // null jika source = package_rate
      "pricing_rule_name": "Weekday Standard",
      "package_id": null,              // null jika source = pricing_rule
      "package_name": null,
      "price_per_minute": "150.00",
      "fixed_price": null,
      "day_type": "weekday",
      "snapshot_at": "2026-07-03T10:00:00+07:00"
    }
    ```
  - `started_at` (DateTimeField) — kapan segmen ini dimulai
  - `ended_at` (DateTimeField, null=True, blank=True) — null berarti segmen masih aktif (table sedang dipakai)
  - `duration_minutes` (DecimalField, max_digits=10, decimal_places=2, null=True, blank=True) — dihitung saat segmen ditutup
  - `amount` (DecimalField, max_digits=12, decimal_places=2, null=True, blank=True) — biaya segmen ini (duration_minutes × price_per_minute dari snapshot, atau proporsional untuk fixed_duration package)
- **Validation Rules:**
  - `rate_source_snapshot` harus valid JSON dengan struktur di atas
  - `started_at` tidak boleh lebih besar dari `ended_at`
  - Satu `table` hanya boleh muncul di satu `SessionTableLog` dengan `ended_at=null` (satu meja tidak bisa dipakai dua sesi bersamaan)
  - Saat create segmen baru untuk sesi yang sama, pastikan tidak ada segmen aktif (`ended_at=null`) lain untuk sesi yang sama (hanya boleh satu segmen aktif per sesi)
- **Meta:**
  - `ordering = ['started_at']`
  - `indexes = [Index(fields=['session', 'ended_at']), Index(fields=['table', 'ended_at'])]`

### Service Functions (sessions/services.py)
Semua fungsi service menerima parameter eksplisit dan return value, tidak bergantung pada request context. Dipanggil dari ViewSet actions.

1. **`resolve_pricing_rule(outlet_id, table_type_id, timestamp=None) → PricingRule | None`**
   - Mencari PricingRule yang match berdasarkan: outlet, day_type (weekday/weekend/specific_date), time range (start_time ≤ timestamp.time() < end_time), table_type (nullable = berlaku semua).
   - Jika beberapa rule match, pilih yang `priority` tertinggi.
   - Jika tidak ada yang match, raise ValidationError (harus ada minimal 1 rule supaya bisa main).
   - Return PricingRule object, atau None jika tidak ditemukan.

2. **`build_rate_snapshot(source_type, pricing_rule=None, package=None) → dict`**
   - Membangun rate_source_snapshot JSON dari PricingRule atau Package yang berlaku.
   - Untuk `pricing_rule`: price_per_minute dari rule, plus metadata rule.
   - Untuk `package_rate` (open_loss dengan price_per_minute sendiri): price_per_minute dari package, plus metadata package.
   - Untuk `package_rate` (fixed_duration/happy_hour): price_per_minute = null, fixed_price dari package.

3. **`calculate_session_totals(session) → (subtotal, additional_fee_total, total_amount)`**
   - Jika session.package bertipe `fixed_duration` atau `happy_hour`: subtotal = package.fixed_price.
   - Jika session.package bertipe `open_loss` atau `per_minute` atau tanpa package: subtotal = sum semua SessionTableLog.amount.
   - Ambil semua AdditionalFee dengan `is_active=True` dan `outlet_id` = session.outlet_id.
   - Untuk setiap fee: jika type='percentage' → fee_amount = subtotal × (value/100); jika type='fixed' → fee_amount = value.
   - additional_fee_total = sum semua fee_amount.
   - total_amount = subtotal + additional_fee_total.
   - Return tuple.

4. **`calculate_current_cost(session) → dict`**
   - Menghitung estimasi biaya on-the-fly untuk sesi running.
   - Iterasi semua SessionTableLog milik session:
     - Untuk segmen yang sudah closed: gunakan amount yang sudah tersimpan.
     - Untuk segmen yang masih aktif (ended_at=null): hitung durasi dari started_at sampai now, lalu kalikan dengan price_per_minute dari rate_source_snapshot (atau jika package fixed_duration, biaya tetap = fixed_price).
   - Return dict: `{running_duration_minutes, estimated_subtotal, additional_fee_total, estimated_total}`.

5. **`close_session(session, user) → None`**
   - Tutup semua SessionTableLog yang masih aktif (set ended_at=now, hitung duration_minutes dan amount).
   - Hitung subtotal, additional_fee_total, total_amount via `calculate_session_totals`.
   - Set session.status='completed', session.ended_at=now, session.officer_end=user, session.subtotal, session.additional_fee_total, session.total_amount.
   - Update semua table terkait (yang di SessionTableLog dengan ended_at baru saja di-set) ke status='available'.
   - Simpan session dan table logs.

6. **`cancel_session(session, user, cancel_reason) → None`**
   - Validasi: hanya sesi running yang bisa dicancel.
   - Tutup semua SessionTableLog yang masih aktif (set ended_at=now, amount=0, duration_minutes sesuai aktual tapi tidak dihitung revenue).
   - Set session.status='cancelled', session.ended_at=now, session.officer_end=user, session.cancel_reason=cancel_reason.
   - Semua field finansial (subtotal, additional_fee_total, total_amount) tetap null.
   - Update semua meja terkait ke status='available'.

7. **`transfer_table(session, from_table, to_table) → None`**
   - Validasi: session.status='running', to_table.status='available', to_table.outlet_id == session.outlet_id.
   - Tutup SessionTableLog aktif di from_table (set ended_at=now, hitung duration_minutes + amount).
   - Update from_table ke status='available'.
   - Pilih pricing: gunakan `resolve_pricing_rule` untuk to_table.table_type (atau gunakan rate dari package jika ada).
   - Build snapshot via `build_rate_snapshot`.
   - Buat SessionTableLog baru untuk to_table (started_at=now, ended_at=null).
   - Update to_table ke status='occupied'.
   - Simpan semua perubahan.

[Files]
Membuat app Django baru `sessions` dengan model, serializer, views, urls, services, dan tests. Memodifikasi file konfigurasi project untuk registrasi app baru.

### New Files
- **`sessions/__init__.py`** — Package init (kosong)
- **`sessions/apps.py`** — Django AppConfig untuk `sessions`
  ```python
  class SessionsConfig(AppConfig):
      default_auto_field = 'django.db.models.BigAutoField'
      name = 'sessions'
  ```
- **`sessions/models.py`** — Model PlaySession dan SessionTableLog (lihat [Types])
- **`sessions/services.py`** — Service functions: `resolve_pricing_rule`, `build_rate_snapshot`, `calculate_session_totals`, `calculate_current_cost`, `close_session`, `cancel_session`, `transfer_table` (lihat [Types] untuk detail)
- **`sessions/serializers.py`** — Serializers:
  - `SessionTableLogSerializer` (ModelSerializer untuk SessionTableLog)
  - `PlaySessionSerializer` (ModelSerializer untuk PlaySession) — include table_logs nested (read-only untuk list/retrieve, write-only untuk create) + custom actions serializers
  - `PlaySessionStartSerializer` — untuk action `start`: customer_name, customer_phone, initial_table, package (opsional)
  - `PlaySessionCancelSerializer` — untuk action `cancel`: cancel_reason
  - `PlaySessionTransferSerializer` — untuk action `transfer_table`: to_table
- **`sessions/views.py`** — ViewSets dan actions:
  - `PlaySessionViewSet(viewsets.ModelViewSet)` — CRUD + custom actions
    - `start` (POST /api/sessions/start/) — buat sesi baru
    - `current_cost` (GET /api/sessions/{id}/current_cost/) — on-the-fly cost
    - `end` (POST /api/sessions/{id}/end/) — tutup sesi
    - `cancel` (POST /api/sessions/{id}/cancel/) — batalkan sesi (admin only)
    - `transfer_table` (POST /api/sessions/{id}/transfer_table/) — transfer meja
  - Permission logic: officer untuk start/end/transfer/current_cost; admin untuk cancel; semua role untuk list/retrieve (dengan scoping outlet)
- **`sessions/urls.py`** — URL routing dengan DefaultRouter + custom action routes
  ```python
  app_name = 'sessions'
  router = DefaultRouter()
  router.register(r'sessions', PlaySessionViewSet, basename='playsession')
  urlpatterns = [path('', include(router.urls))]
  ```
- **`sessions/admin.py`** — Admin registration untuk PlaySession dan SessionTableLog
- **`sessions/tests.py`** — Comprehensive test suite (lihat [Testing])
- **`sessions/migrations/__init__.py`** — Migration package init

### Modified Files
- **`core/settings/base.py`** — Tambahkan `'sessions'` ke `INSTALLED_APPS`
- **`core/urls.py`** — Tambahkan `path('api/', include('sessions.urls'))`

[Functions]
Mendefinisikan seluruh fungsi service, custom ViewSet actions, dan validasi yang diperlukan untuk modul Play Session.

### New Service Functions (sessions/services.py)
1. **`resolve_pricing_rule(outlet_id: int, table_type_id: int, timestamp: datetime = None) → PricingRule | None`**
   - Purpose: Mencari PricingRule yang match untuk kombinasi outlet, table_type, dan waktu tertentu.
   - Logic: Filter PricingRule by outlet_id, is_active=True, table_type_id (nullable = all). Tentukan day_type dari timestamp (weekday/Sat-Sun/specific_date). Filter by day_type match. Filter by time range (start_time ≤ timestamp.time() < end_time). Order by -priority, ambil first.

2. **`build_rate_snapshot(source_type: str, pricing_rule: PricingRule = None, package: Package = None) → dict`**
   - Purpose: Membangun JSON snapshot tarif yang berlaku untuk disimpan di SessionTableLog.
   - Logic: Jika pricing_rule → extract price_per_minute, name, id, day_type. Jika package → extract price_per_minute (jika open_loss), fixed_price (jika fixed_duration/happy_hour), name, id.

3. **`calculate_session_totals(session: PlaySession) → tuple[Decimal, Decimal, Decimal]`**
   - Purpose: Menghitung subtotal, additional fee, dan total dari session.
   - Logic: Lihat [Types] untuk detail algoritma.

4. **`calculate_current_cost(session: PlaySession) → dict`**
   - Purpose: Estimasi biaya on-the-fly untuk sesi running.
   - Logic: Lihat [Types] untuk detail algoritma.

5. **`close_session(session: PlaySession, user: User) → PlaySession`**
   - Purpose: Menutup sesi, finalisasi biaya, update status meja.
   - Logic: Lihat [Types] untuk detail.

6. **`cancel_session(session: PlaySession, user: User, cancel_reason: str) → PlaySession`**
   - Purpose: Membatalkan sesi (admin only).
   - Logic: Lihat [Types] untuk detail.

7. **`transfer_table(session: PlaySession, from_table: Table, to_table: Table) → SessionTableLog`**
   - Purpose: Transfer sesi ke meja lain, tutup segmen lama, buka segmen baru.
   - Logic: Lihat [Types] untuk detail.

### New ViewSet Actions (sessions/views.py)
Semua actions berikut berada di `PlaySessionViewSet`:

1. **`start(self, request)` — POST /api/sessions/start/**
   - Purpose: Membuka sesi permainan baru.
   - Flow:
     1. Validasi officer punya Shift open (shift.status='open', shift.officer=user, shift.outlet=user.outlet).
     2. Validasi initial_table tersedia (status='available', outlet=user.outlet).
     3. Validasi package (jika ada) milik outlet yang sama.
     4. Buat PlaySession dengan status='running', officer_start=user, shift=shift_open.
     5. Resolve pricing rule untuk initial_table.
     6. Build rate snapshot.
     7. Buat SessionTableLog (started_at=now, ended_at=null).
     8. Update initial_table ke status='occupied'.
     9. Return PlaySession dengan nested table_logs.

2. **`end(self, request, pk=None)` — POST /api/sessions/{id}/end/**
   - Purpose: Menutup sesi yang sedang berjalan.
   - Flow:
     1. Validasi session.status='running' dan milik outlet user.
     2. Panggil `close_session(session, user)`.
     3. Return session yang sudah di-finalisasi.

3. **`cancel(self, request, pk=None)` — POST /api/sessions/{id}/cancel/**
   - Purpose: Membatalkan sesi (admin only). Validasi admin scope outlet.
   - Flow:
     1. Validasi user.is_admin.
     2. Validasi session.status='running'.
     3. Validasi cancel_reason tidak kosong.
     4. Panggil `cancel_session(session, user, cancel_reason)`.
     5. Return session yang dibatalkan.

4. **`transfer_table(self, request, pk=None)` — POST /api/sessions/{id}/transfer_table/**
   - Purpose: Transfer sesi ke meja lain.
   - Flow:
     1. Validasi session.status='running' dan milik outlet user.
     2. Validasi to_table.status='available' dan to_table.outlet == session.outlet.
     3. Cari SessionTableLog aktif (ended_at=null) → from_table.
     4. Panggil `transfer_table(session, from_table, to_table)`.
     5. Return session dengan table_logs terbaru.

5. **`current_cost(self, request, pk=None)` — GET /api/sessions/{id}/current_cost/**
   - Purpose: Mendapatkan estimasi biaya terkini.
   - Flow:
     1. Validasi akses ke session.
     2. Panggil `calculate_current_cost(session)`.
     3. Return dict dengan running_duration_minutes, estimated_subtotal, additional_fee_total, estimated_total.

### Existing Functions (modified)
Tidak ada fungsi existing yang dimodifikasi. Hanya penambahan app baru.

[Classes]
Mendefinisikan class baru untuk model, serializer, dan ViewSet. Tidak ada class existing yang perlu dimodifikasi.

### New Classes
1. **`PlaySession(models.Model)` — `sessions/models.py`**
   - Fields: outlet, shift, customer_name, customer_phone, initial_table, package, status, started_at, ended_at, officer_start, officer_end, subtotal, additional_fee_total, total_amount, cancel_reason, created_at
   - Inner class `Status(models.TextChoices)`: RUNNING, COMPLETED, CANCELLED
   - Static method `validate_invariants(...)` — pola sama seperti Shift, Package
   - Method `clean()` — panggil validate_invariants
   - Method `save()` — handle transisi status (running→completed/cancelled)
   - Meta: ordering, indexes

2. **`SessionTableLog(models.Model)` — `sessions/models.py`**
   - Fields: session, table, rate_source_type, rate_source_snapshot (JSONField), started_at, ended_at, duration_minutes, amount
   - Inner class `RateSourceType(models.TextChoices)`: PRICING_RULE, PACKAGE_RATE
   - Static method `validate_invariants(...)` — validasi table tidak dipakai ganda, validasi one-active-segment-per-session
   - Method `clean()`
   - Meta: ordering, indexes (session+ended_at, table+ended_at)

3. **`PlaySessionSerializer(serializers.ModelSerializer)` — `sessions/serializers.py`**
   - Meta fields: semua field + nested table_logs (read-only)
   - read_only_fields: id, started_at, ended_at, officer_start, officer_end, subtotal, additional_fee_total, total_amount, created_at
   - Method `validate()` — delegate ke PlaySession.validate_invariants + validasi shift open + validasi table available

4. **`SessionTableLogSerializer(serializers.ModelSerializer)` — `sessions/serializers.py`**
   - Meta fields: semua field
   - read_only_fields: started_at, duration_minutes, amount

5. **`PlaySessionStartSerializer(serializers.Serializer)` — `sessions/serializers.py`**
   - Fields: customer_name (required), customer_phone (optional), initial_table (required, PK), package (optional, PK)
   - Validate: initial_table exists & available & same outlet; package exists & same outlet (jika diisi)

6. **`PlaySessionCancelSerializer(serializers.Serializer)` — `sessions/serializers.py`**
   - Fields: cancel_reason (required, CharField, min_length=5)

7. **`PlaySessionTransferSerializer(serializers.Serializer)` — `sessions/serializers.py`**
   - Fields: to_table (required, PK)
   - Validate: to_table exists & available & same outlet

8. **`PlaySessionViewSet(viewsets.ModelViewSet)` — `sessions/views.py`**
   - queryset: PlaySession.objects.select_related('outlet', 'shift', 'initial_table', 'package', 'officer_start', 'officer_end').prefetch_related('table_logs__table')
   - serializer_class: PlaySessionSerializer
   - filter_backends: DjangoFilterBackend, SearchFilter, OrderingFilter
   - filterset_fields: status, outlet
   - search_fields: customer_name, customer_phone
   - ordering_fields: started_at, ended_at, total_amount
   - Permission: officer untuk start/end/transfer/current_cost; admin untuk cancel; IsAuthenticated untuk list/retrieve
   - get_queryset(): scope by outlet (non-super-admin)
   - Custom actions: start, end, cancel, transfer_table, current_cost (dengan decorator @action)

[Dependencies]
Tidak ada package baru yang diperlukan. Menggunakan dependencies existing: Django, DRF, django-filter, SimpleJWT, drf-spectacular (semua sudah terinstall).

### Schema Updates
Setelah model dibuat, jalankan:
```bash
python manage.py makemigrations sessions
python manage.py migrate
```

### Third-party Packages
Tidak ada tambahan. `JSONField` sudah built-in di Django (PostgreSQL native, SQLite sebagai TEXT).

[Testing]
Membuat comprehensive test suite di `sessions/tests.py` mencakup semua alur bisnis Play Session.

### Test Structure
Menggunakan `APITestCase` dengan setup data: tenant, outlet, table types, tables, pricing rules, packages, additional fees, users (officer, admin, super_admin), dan shift open.

### Test Cases (minimal)

**Start Session:**
1. Officer dapat membuka sesi baru dengan meja available + shift open
2. Officer tidak bisa membuka sesi tanpa shift open (harus error)
3. Officer tidak bisa membuka sesi di meja occupied/maintenance
4. Officer dapat membuka sesi dengan package (package.outlet == session.outlet)
5. Officer tidak bisa membuka sesi dengan package dari outlet lain
6. Saat sesi dibuka, meja berubah status jadi occupied
7. SessionTableLog dibuat dengan benar (ended_at=null, rate_source_snapshot terisi)
8. customer_phone opsional (boleh kosong)

**Current Cost:**
9. GET current_cost mengembalikan estimasi biaya (duration > 0, estimated_subtotal > 0)
10. Current cost untuk package fixed_duration mengembalikan fixed_price sebagai subtotal
11. Additional fee ikut dihitung dalam estimated_total

**End Session:**
12. Officer dapat menutup sesi running miliknya
13. Saat sesi ditutup, semua SessionTableLog ter-finalisasi (ended_at + duration_minutes + amount terisi)
14. subtotal, additional_fee_total, total_amount terhitung dengan benar (sesuai pricing rule + additional fees)
15. Semua meja terkait kembali available
16. Sesi dengan package fixed_duration: subtotal = fixed_price (bukan per-menit)
17. Package happy_hour: subtotal = fixed_price
18. Tidak bisa menutup sesi yang sudah completed/cancelled

**Cancel Session:**
19. Admin dapat membatalkan sesi running di outlet-nya
20. Officer tidak bisa membatalkan sesi (403 Forbidden)
21. Admin dari outlet lain tidak bisa membatalkan sesi
22. Cancel harus menyertakan cancel_reason
23. Sesi yang sudah completed tidak bisa dibatalkan
24. Setelah cancel, meja kembali available
25. Setelah cancel, subtotal/additional_fee_total/total_amount tetap null (tidak ada revenue)

**Transfer Table:**
26. Officer dapat transfer sesi ke meja available lain
27. SessionTableLog lama tertutup (ended_at + amount terisi)
28. SessionTableLog baru terbuka (ended_at=null)
29. Meja lama kembali available, meja baru jadi occupied
30. Tidak bisa transfer ke meja yang occupied/maintenance
31. Tidak bisa transfer ke meja dari outlet lain
32. Tidak bisa transfer sesi yang sudah completed/cancelled
33. Transfer mempertahankan akumulasi biaya (total = old_segment + new_segment)

**Permission & Scoping:**
34. Officer hanya melihat sesi di outlet-nya
35. Officer hanya melihat sesi yang dia buka
36. Admin melihat semua sesi di outlet-nya
37. Officer tidak bisa mengakses sesi officer lain di outlet yang sama (untuk modifikasi)
38. Super Admin melihat semua sesi

**Pricing Resolution:**
39. Pricing rule dipilih berdasarkan day_type + time window + priority
40. Rate snapshot tersimpan dengan benar di SessionTableLog

[Implementation Order]
Implementasi dilakukan secara bertahap dari model → service → serializer → views → tests untuk memastikan setiap layer berfungsi sebelum layer berikutnya dibangun.

1. **Step 1: Buat struktur app sessions** — Buat direktori `sessions/` dengan `__init__.py`, `apps.py`, `admin.py` (kosong dulu), `migrations/__init__.py`

2. **Step 2: Implementasi model PlaySession & SessionTableLog** — Buat `sessions/models.py` dengan kedua model lengkap (fields, choices, Meta, validate_invariants, clean, save)

3. **Step 3: Registrasi app + jalankan migrasi** — Tambahkan `'sessions'` ke `INSTALLED_APPS` di `core/settings/base.py`, jalankan `makemigrations sessions` dan `migrate`

4. **Step 4: Implementasi service layer** — Buat `sessions/services.py` dengan semua fungsi service (resolve_pricing_rule, build_rate_snapshot, calculate_session_totals, calculate_current_cost, close_session, cancel_session, transfer_table)

5. **Step 5: Implementasi serializers** — Buat `sessions/serializers.py` dengan PlaySessionSerializer, SessionTableLogSerializer, PlaySessionStartSerializer, PlaySessionCancelSerializer, PlaySessionTransferSerializer

6. **Step 6: Implementasi ViewSet + custom actions** — Buat `sessions/views.py` dengan PlaySessionViewSet dan semua @action methods (start, end, cancel, transfer_table, current_cost)

7. **Step 7: Implementasi URL routing** — Buat `sessions/urls.py` dengan DefaultRouter, tambahkan `path('api/', include('sessions.urls'))` ke `core/urls.py`

8. **Step 8: Implementasi admin** — Update `sessions/admin.py` dengan ModelAdmin untuk PlaySession dan SessionTableLog

9. **Step 9: Implementasi test suite** — Buat `sessions/tests.py` dengan semua test cases yang tercantum di [Testing]

10. **Step 10: Verifikasi + run tests** — Jalankan `python manage.py test sessions -v2` untuk memastikan semua test pass, perbaiki bug yang ditemukan
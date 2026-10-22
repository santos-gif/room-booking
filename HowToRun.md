# HowToRun — Discussion Room Booking

Aplikasi pemesanan ruang diskusi (Room 1 / Room 2) untuk mahasiswa Pradita.
Stack: Angular (frontend), FastAPI (backend), Supabase (database + auth), Google Calendar (jadwal ruangan).

## 1. Prasyarat

- Node.js dan npm, Python 3.11+ (diuji dengan 3.13)
- Vercel CLI (`npm i -g vercel`) — frontend dan backend dijalankan bersama lewat `vercel dev`
- Project Supabase dan Google Cloud OAuth client (Calendar API aktif), plus dua kalender Google (Room 1, Room 2)
- Google Chrome (dipakai oleh Playwright)

## 2. Konfigurasi (satu kali)

Backend — salin `backend/.env.example` menjadi `backend/.env.local`, lalu isi:
`SUPABASE_URL`, `SUPABASE_KEY` (publishable key), `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`GOOGLE_CALENDAR_ROOM_1_ID`, `GOOGLE_CALENDAR_ROOM_2_ID`, `GOOGLE_TOKEN_ENCRYPTION_KEY` (Fernet key),
`CRON_SECRET` dan `SUPABASE_BACKEND_RPC_SECRET` (acak, masing-masing minimal 32 karakter dan berbeda).
Untuk lokal: `GOOGLE_REDIRECT_URI=http://localhost:3000/api/v1/google-auth/oauth2callback`,
`FRONTEND_URL=http://localhost:3000`, `COOKIE_SECURE=false`.
Daftarkan redirect URI yang sama di Google Cloud Console.

Frontend — `frontend/.env.local`:

```
NG_APP_API_URL=http://localhost:3000/api/v1
```

Database — jalankan semua file di `supabase/migrations/` berurutan (nama file = urutan) pada project Supabase.

## 3. Instalasi

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e . pytest

# frontend
cd ../frontend
npm install
```

## 4. Menjalankan aplikasi

Dari root repo:

```bash
vercel dev --listen 3000
```

Buka http://localhost:3000 lalu login dengan akun `@student.pradita.ac.id` atau `@pradita.ac.id`.
Login pertama meminta NIM dan jurusan (onboarding), setelah itu masuk ke "My bookings".

## 5. Menjalankan unit test

```bash
# backend (55 test)
cd backend
.venv\Scripts\python.exe -m pytest -q

# frontend (51 test, 15 file)
cd frontend
npx ng test --no-watch
```

Pemeriksaan tampilan (data API di-mock, tanpa login) di ukuran 390×844 dan 1440×900:

```bash
cd frontend
npx playwright test anonymous.ui anonymous.flows
```

Peta kode backend (struktur folder, aturan impor, "mau ubah X → lihat file Y"): `backend/ARCHITECTURE.md`.

Build produksi: `cd frontend && npx ng build`.

## 6. Alur demo singkat

1. Login Google dengan akun kampus → isi NIM dan jurusan.
2. "Book a room" → pilih tanggal (hari kerja), ruangan, jam → Confirm.
3. Event muncul di Google Calendar ruangan tersebut; booking tampil di "My bookings".
4. Booking ke-4 ditolak (batas 3 booking aktif per mahasiswa).
5. Cancel booking → slot kembali tersedia dan event Calendar dihapus.
6. Profile → ubah NIM atau jurusan.

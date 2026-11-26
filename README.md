# Discussion Room Booking

Aplikasi pemesanan ruang diskusi (Room 1 dan Room 2) untuk mahasiswa Pradita. Slot satu jam, hari kerja
08:00-17:00 WIB, maksimal 3 booking aktif per mahasiswa. Setiap booking menjadi event di Google Calendar ruangan.
Staf bisa menutup ruangan untuk rentang tanggal dan mengambil alih satu slot; mahasiswa yang terdampak diberi tahu di aplikasi.

- Frontend: Angular 22 (signals, Angular Material), folder `frontend/`
- Backend: FastAPI (Python 3.11+), folder `backend/`
- Database dan login: Supabase (Postgres + Auth), skema di `supabase/migrations/`
- Jadwal: Google Calendar, satu service account menulis ke kedua kalender
- Hosting: Vercel (frontend dan backend sebagai dua service, lihat `vercel.json`)

Akses: aplikasi produksi https://discussion-room-booking-pita.vercel.app (login akun `@student.pradita.ac.id`
atau `@pradita.ac.id`). Video demo: https://drive.google.com/drive/folders/1w3qJziggvK4wHWlg2-z_DbvWK-4eC_5x?usp=drive_link

## 1. Instal ulang dari clone baru

Prasyarat: Git, Node.js + npm, Python 3.11+ (diuji 3.13), Vercel CLI (`npm i -g vercel`).

```bash
git clone https://github.com/santos-gif/room-booking.git
cd room-booking

# backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows; Linux/macOS: source .venv/bin/activate
pip install -e . pytest
cd ..

# frontend
cd frontend
npm install
cd ..
```

## 2. Konfigurasi (satu kali)

Backend: salin `backend/.env.example` menjadi `backend/.env.local` dan isi semua nama di dalamnya
(`SUPABASE_URL`, `SUPABASE_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_SERVICE_ACCOUNT_JSON`,
`GOOGLE_CALENDAR_ROOM_1_ID`, `GOOGLE_CALENDAR_ROOM_2_ID`, `CRON_SECRET`, `SUPABASE_BACKEND_RPC_SECRET`, dan seterusnya).
`GOOGLE_SERVICE_ACCOUNT_JSON` ditulis satu baris. Bagikan kedua kalender ruangan ke email service account dengan izin
"Make changes to events", kalau tidak, booking gagal dengan 403. Dua secret acak minimal 32 karakter dan berbeda.
Lokal: `GOOGLE_REDIRECT_URI=http://localhost:3000/api/v1/google-auth/oauth2callback`, `FRONTEND_URL=http://localhost:3000`,
`COOKIE_SECURE=false`. Daftarkan redirect URI yang sama di Google Cloud Console.

Frontend: `frontend/.env.local` berisi `NG_APP_API_URL=http://localhost:3000/api/v1`.

Database: di SQL editor Supabase jalankan lebih dulu `supabase/main.sql` (hubungan ke Supabase Auth, RLS, kebijakan
bawaan, fungsi aturan booking), lalu semua file di `supabase/migrations/` berurutan menurut nama (diawali tanggal).
`main.sql` kini juga membuat tabel dasar `users`, `appointments` dan `google_refresh_tokens`. Urutan ini sudah diuji pada
Postgres kosong (Docker, dengan stub Supabase): `main.sql` lalu 16 file bertanggal lolos semua. Hasilnya berbeda dari
produksi pada beberapa policy dan hak kolom (lihat issue #19 dan #20).
Migrasi `202611050001_closure_no_overlap.sql` berhenti dengan pesan jelas jika masih ada dua penutupan yang tumpang tindih.

Staf: tidak ada layar untuk mengangkat staf. Jalankan di SQL editor:
`UPDATE public.users SET role = 'staff' WHERE email = '<email>';` (mahasiswa tidak bisa mengubah kolom `role`).

## 3. Menjalankan, menguji, membangun

```bash
vercel dev --listen 3000                 # dari root repo; buka http://localhost:3000

cd backend && .venv\Scripts\python.exe -m pytest -q       # 134 test
cd frontend && npx ng test --no-watch                     # 139 test
cd frontend && npx ng build                               # build produksi
node .claude/skills/verify-all/check-file-sizes.js        # aturan 150 baris/kolom per file
```

## 4. Deploy ke Vercel

1. Impor repo di Vercel. `vercel.json` di root mendefinisikan dua service (`frontend/` dan `backend/`), header keamanan,
   rewrite `/api/*` ke backend, dan cron harian `10 0 * * *` ke `/api/v1/appointments/reconcile`.
2. Isi environment variable yang sama dengan `backend/.env.example` di Vercel (production, preview, development);
   `GOOGLE_REDIRECT_URI` dan `FRONTEND_URL` memakai domain produksi, `COOKIE_SECURE=true`. `CRON_SECRET` wajib karena
   cron memanggil rute rekonsiliasi dengan header `Authorization: Bearer`.
3. Deploy hanya lewat GitHub Actions (`.github/workflows/ci.yml`): test dan build harus lulus dulu. Push ke `v1.0_dev`
   membuat preview untuk diuji, push ke `v1.1` men-deploy produksi; `main` dan `v1.0` hanya diuji. Deploy otomatis Vercel
   dimatikan untuk keempat cabang di `vercel.json`. Secret GitHub yang dibutuhkan: `VERCEL_TOKEN`, `VERCEL_ORG_ID`,
   `VERCEL_PROJECT_ID`. Terapkan migrasi baru ke Supabase lebih dulu.
4. Cek: buka situs, login, buat booking, lihat event di kalender, lalu lihat log di Vercel (Project > Logs).

## 5. Dokumen lain

- `HowToRun.md`: langkah jalan dan alur demo singkat.
- `docs/security-test-results.md`: hasil uji keamanan dan catatan perubahan keamanan.
- `docs/troubleshooting.md`: contoh log aman, penyebab error, tindakan perbaikan.
- `checklist_mvp.md`: daftar yang sudah diperiksa, keterbatasan, dan risiko yang diketahui.
- `backend/ARCHITECTURE.md`, `frontend/ARCHITECTURE.md`: peta kode dan aturan folder.
Link Website: https://discussion-room-booking-pita.vercel.app/
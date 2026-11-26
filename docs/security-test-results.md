# Hasil uji keamanan dan catatan perubahan

Dijalankan 2026-11-26 pada cabang `v1.0_dev`. Bagian A dan C dijalankan ulang pada tanggal itu. Bagian B dan D
dikerjakan pada 2026-11-19. Bagian E diambil dari audit lama dan TIDAK dijalankan ulang.

## A. Uji otomatis

| Pemeriksaan | Hasil |
|---|---|
| Backend lengkap (`pytest -q`) | 134 lulus |
| Backend terkait keamanan (16 file, perintah di bawah) | 83 lulus |
| Frontend lengkap (`ng test --no-watch`, zona waktu UTC) | 139 lulus, 36 file |
| Lint backend (`ruff check --select F,E9`) | bersih |
| Build produksi (`ng build`) | berhasil |

```bash
cd backend && python -m pytest -q tests/test_auth_session.py tests/test_crash_defence_login.py \
  tests/test_crash_defence_data.py tests/test_hostile_input.py tests/test_revoke_session.py tests/test_staff.py \
  tests/test_staff_rules.py tests/test_config.py tests/test_google_callback.py tests/test_google_credentials.py \
  tests/test_google_oauth.py tests/test_verify_safety.py tests/test_self_overlap.py tests/test_closure_overlap.py \
  tests/test_booking_rules.py tests/test_lead_rule.py
```

Yang dibuktikan (nama test ada di `backend/tests/`):

- Login: domain email diperiksa persis; hanya identitas yang diminta; kegagalan mengarahkan ulang tanpa detail mentah.
- Sesi: refresh memutar token; ditolak sepekan setelah login (batas 7 hari, lihat temuan 1); logout mencabut sesi.
- CSRF dan input jahat: header non-ASCII 403/401; bypass hanya untuk GET callback; dokumentasi API mati; jawaban tidak
  di-cache; input ekstrem ditolak (422); error tak terduga dijawab 500 generik.
- Konfigurasi: secret minimal 32 karakter dan berbeda; kunci service account rusak tidak pernah ditampilkan.
- Staf: hanya staf lolos; override yang gagal tidak membatalkan siapa pun.
- Integritas: booking di ruangan tertutup ditolak; satu orang satu ruangan per jam; penutupan tumpang tindih ditolak.

Pipeline GitHub Actions (`.github/workflows/ci.yml`) menjalankan test dan build pada setiap push; deploy hanya jika semua
lulus. Run pertama gagal dan deploy dilewati: https://github.com/santos-gif/room-booking/actions/runs/45749441084
(gambar: `screenshots/p11-01-red-run-deploy-skipped.png`).

## B. Pemeriksaan database (hanya baca, produksi)

- `authenticated` tidak punya hak UPDATE pada `users.role`; hanya `nim` dan `major`.
- Semua fungsi `SECURITY DEFINER` mengunci `search_path`; RLS aktif pada 6 tabel.
- Fungsi yang bisa dipanggil `anon` memeriksa secret backend atau identitas pemanggil.
- SQL repo diputar ulang pada Postgres kosong (Docker): `supabase/main.sql` dan 16 migrasi lulus. Hasilnya lebih ketat
  daripada produksi pada beberapa policy dan hak kolom (temuan 5).

## C. Audit dependensi (`npm audit --omit=dev`)

10 temuan: 3 tinggi, 6 sedang, 1 rendah, 0 kritis. Semuanya alat build dan test:
tinggi `undici`, `vite`, `zod`; sedang `@ngx-env/builder`, `vitest`, `@vitest/mocker`, `fast-uri`, `glob`, `minimatch`;
rendah `@angular/build`. Perbaikan (`npm audit fix`) belum diterapkan. `pip-audit` untuk backend belum dijalankan.

## D. Temuan tinjauan kode (metode skill `security-audit` Cloudflare, sebagian)

Tinjauan sumber oleh satu agen, tanpa verifikator independen, tanpa menjalankan kode proyek.

| # | Temuan | Tingkat | Status |
|---|---|---|---|
| 1 | Batas sesi 7 hari mungkin tidak pernah berlaku (cara membaca klaim `amr`) | perlu validasi | issue #1 |
| 2 | Token Google lama masih tersimpan di database | rendah | issue #2, proposal disetujui |
| 3 | Pemeriksaan CSRF dilewati untuk semua metode di path callback OAuth | informasi | diperbaiki, issue #3 |
| 4 | CSP mengizinkan inline style | informasi | issue #4 |
| 5 | Policy dan hak kolom produksi lebih longgar daripada SQL repo | sedang | issue #20 |

## E. Audit manual sebelumnya (dari `checklist_mvp.md`, tidak dijalankan ulang)

Review kode, fuzzing 4.500+ request, dan pengujian dari luar terhadap situs produksi. Daftar risiko ada di
`checklist_mvp.md`, bagian "Risiko keamanan yang diketahui" (sebagian sudah usang, misalnya lama sesi 30 hari).

## F. Catatan perubahan yang relevan dengan keamanan

| Perubahan | Dampak | Status |
|---|---|---|
| Satu service account menulis ke kalender | Mahasiswa tidak lagi memberi akses Calendar | aktif |
| Peran `staff` hanya lewat SQL admin | Mahasiswa tidak bisa menaikkan peran | diterapkan |
| Penutupan, override, notifikasi (RLS), log audit staf | Tindakan staf tercatat | diterapkan |
| Satu orang satu ruangan per jam | Menutup booking dua ruangan di jam sama | diterapkan |
| Batas sesi 7 hari | Lihat temuan 1 | di kode, belum terbukti |
| CSRF bypass hanya untuk GET | Rute POST baru tidak bisa melewati CSRF | di `v1.0_dev` |
| Penutupan tidak boleh tumpang tindih | Ditolak form dan backend; constraint database | constraint belum diterapkan (#15) |
| Deploy hanya setelah test lulus; auto-deploy Vercel mati | Kode gagal test tidak tayang | di `v1.0_dev` |

## G. Belum diuji

Pemindai exploit otomatis, `pip-audit`, uji beban, sesi staf asli terhadap produksi, batas 7 hari dengan token asli,
dan aturan rate limit di dashboard Vercel.

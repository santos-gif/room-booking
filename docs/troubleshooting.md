# Log, penyebab error, dan tindakan perbaikan

Pesan log di bawah diambil persis dari kode backend. Contoh barisnya disusun dari pesan itu dengan ID disamarkan
(`<appointment-id>`); bukan salinan log produksi.

## Cara membaca log

- Vercel > proyek > Logs, saring dengan path `/api/v1/`. Paket Hobby menyimpan log hanya sebentar (sekitar 1 jam).
- GitHub > Actions > pilih run: job merah menunjukkan test atau build yang gagal.

## Aturan log yang aman

- Boleh dicatat: ID appointment/event, nama operasi, jejak error (stack trace) di server.
- Jangan dicatat atau disalin: cookie, access/refresh token, `GOOGLE_SERVICE_ACCOUNT_JSON`, secret, email atau NIM orang.
- Ke browser hanya dikirim kalimat umum; detail hanya ada di log server (`app/main.py`).

## Booking dan kalender

| Pesan log | Penyebab | Tindakan |
|---|---|---|
| `Database rejected appointment reservation.` | Aturan database: slot terisi, batas 3, ruangan tutup, jam sama | Wajar (409/422) |
| `Google Calendar event creation failed.` | Kalender belum dibagikan ke service account (403), kunci salah, kuota | Lihat catatan 1 |
| `Calendar event exists but booking confirmation failed.` | Event dibuat, database gagal diperbarui | Cron menyelesaikan; cek Supabase |
| `Could not delete the room calendar event.` | Google gagal menghapus saat cancel | Cron mencoba lagi |
| `Google event was deleted but booking cancellation failed.` | Database gagal setelah event hilang | Pemeriksaan berikutnya membatalkan |
| `Room calendar unreachable; keeping appointment <appointment-id>.` | Cek Google gagal; baris sengaja dipertahankan | Jika terus: catatan 1 |
| `Reconciliation budget used up; the remaining rows wait for the next run.` | Batas waktu cron | Tidak perlu tindakan |
| `Appointment <appointment-id> could not be reconciled.` | Data baris tidak konsisten | Periksa `status`, `sync_status`, ID Google |
| `Garbage collection of finished appointments failed.` | Fungsi purge gagal | Cek `SUPABASE_BACKEND_RPC_SECRET` dan migrasi |

Catatan 1: bagikan kedua kalender ruangan ke email service account dengan izin "Make changes to events", lalu periksa
`GOOGLE_SERVICE_ACCOUNT_JSON` (satu baris) di Vercel dan lakukan satu booking uji.

## Login, staf, dan umum

| Pesan log | Penyebab | Tindakan |
|---|---|---|
| `Could not start Google sign-in.` | Konfigurasi OAuth Google tidak lengkap | Isi client ID, secret, redirect URI |
| `Google OAuth token exchange failed.` | Dibatalkan, kode dipakai ulang, redirect URI beda | Samakan URI di Google Console |
| `Supabase Auth failed during Google ID-token sign-in.` | Provider Google Supabase salah atau proyek dijeda | Cek Supabase Auth |
| `Supabase session revocation failed during logout.` | Supabase tidak menjawab | Cookie tetap dihapus |
| `Could not delete the event of staff-cancelled appointment <appointment-id>.` | Google gagal saat tindakan staf | Cron menghapus nanti |
| `Could not remove the staff hold event <event-id> after a failed override.` | Event yatim di kalender | Hapus manual |
| `Unhandled Supabase request failure.` | Supabase mati, kunci salah, migrasi belum diterapkan | Cek status dan `SUPABASE_KEY` |
| `Unhandled server error.` | Bug tak terduga (browser hanya melihat 500 generik) | Baca stack trace, buat issue |

Contoh baris (disanitasi):

```
ERROR app.api.v1.appointment.cancel: Google event was deleted but booking cancellation failed.
WARNING app.api.v1.appointment.verify: Room calendar unreachable; keeping appointment <appointment-id>.
```

## Masalah nyata yang pernah terjadi

| Gejala | Penyebab | Perbaikan | Issue |
|---|---|---|---|
| Booking dijawab 403 `requiredAccessLevel` | Service account hanya boleh membaca kalender | Catatan 1 | #5 |
| Event dihapus di Google tetapi booking tetap ada | Probe memakai `calendars.get` yang dilarang scope | Pakai `events.list` | #6 |
| Run CI merah: jam tampil 02:00, bukan 09:00 | `DatePipe` tidak menerima `Asia/Jakarta` | Pakai `+0700` | #21 |
| Migrasi gagal "already exists" pada database baru | `main.sql` dan migrasi pertama membuat objek yang sama | Migrasi dibuat idempoten | #19 |
| Migrasi penutupan berhenti "Overlapping closures exist" | Dua penutupan satu ruangan beririsan | Reopen salah satu, jalankan lagi | #15 |
| Run CI gagal sebelum test (Node/npm) | Versi runner beda dari lokal | Node 24.15.0 dan npm 12.0.1 dipaku | - |

## Jika pipeline merah

1. Buka run, lihat job yang merah dan bagian Annotations. Job `Deploy to Vercel` dilewati, situs tidak berubah.
2. Jalankan lokal: `cd backend && python -m pytest -q` atau `cd frontend && npx ng test --no-watch`.
3. Perbaiki, commit, push. Run hijau akan men-deploy (`v1.0_dev` preview, `v1.1` produksi).

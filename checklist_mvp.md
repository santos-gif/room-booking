# Checklist MVP — Discussion Room Booking

Terakhir dijalankan: 2026-10-21.

## Ringkasan pengujian

| Pemeriksaan | Hasil |
|---|---|
| Unit test backend (`pytest`, 22 file, 107 test) | PASSED 107/107 |
| Unit test frontend (`ng test`, 29 file, 109 test) | PASSED 109/109 |
| Build produksi (`ng build`) | OK, tanpa peringatan budget |
| Pemeriksaan tampilan 390×844 dan 1440×900 (12 skenario, API di-mock) | PASSED 12/12 |
| Migrasi Supabase `…0004`, `…0005` | Diterapkan, diverifikasi dengan query |
| Pengujian end-to-end langsung (Supabase + Google Calendar sungguhan) | BELUM dijalankan |

## Fitur inti

| # | Fitur | Unit test | Status |
|---|---|---|---|
| 1 | Login Google, hanya `@student.pradita.ac.id` / `@pradita.ac.id` | `test_google_email_domain_validation_is_exact`, `test_google_callback_*` | PASSED |
| 2 | Onboarding NIM + jurusan, ubah profil | `test_onboarding_rejects_unapproved_major_and_nonpositive_nim` | PASSED |
| 3 | Lihat slot: hari kerja, 08:00–17:00 WIB, 1 jam, 2 ruangan | `test_only_future_weekday_booking_hours_are_allowed`, `test_availability_*`, `slot-grid.spec.ts`, `booking-controls.spec.ts` | PASSED |
| 4 | Booking dan sinkron ke Google Calendar ruangan yang dipilih | `test_appointment_persists_and_syncs_calendar_event`, `test_selected_room_uses_its_configured_calendar` | PASSED |
| 5 | Maksimal 3 booking aktif per mahasiswa | `test_availability_closes_every_slot_at_the_booking_limit` (+ trigger database) | PASSED |
| 6 | Lihat dan batalkan booking sendiri | `test_cancellation_uses_the_restricted_state_transition_rpc`, `booking-card.spec.ts` | PASSED |
| 7 | Sesi: refresh token, logout | `test_refresh_uses_and_rotates_supabase_auth_session`, `test_logout_clears_all_auth_cookies`, `auth-refresh-interceptor.spec.ts`, `auth-service.spec.ts` | PASSED |
| 8 | Kalender gagal → booking dibatalkan, slot kembali bebas | `test_calendar_failure_removes_the_booking`, `test_stale_pending_booking_is_undone_never_promoted` | PASSED |
| 9 | Rekonsiliasi harian (cron) dilindungi secret | `test_reconciliation_requires_configured_bearer_secret` | PASSED |

## Input tidak valid, data kosong, loading, kegagalan

| Kasus | Penanganan | Diperiksa |
|---|---|---|
| NIM kosong / jurusan belum dipilih | Pesan error di form | Unit test backend, tampilan |
| Belum ada booking | Kartu "No upcoming bookings" | Tampilan (mock) |
| Memuat data | Skeleton, "Loading availability…", progress bar antar halaman | Tampilan (mock) |
| Server tidak terjangkau / error 5xx | Dialog "An Error Occurred" | Tampilan (mock) |
| Slot sudah diambil / batas 3 booking | Pesan 409 di dialog hasil | Unit test backend |
| Kalender ruangan tidak bisa ditulis service account | Pesan "room calendar is not available" (403) | Unit test backend |

## Keterbatasan yang diketahui

- Aturan 5 menit (slot tidak bisa dipesan kurang dari 5 menit sebelum mulai) hanya dijaga di backend; database belum menolaknya. Judul event Calendar `Discussion Room {1/2}-{Nama} ({NIM})` berlaku untuk booking baru dan update; event yang dibuat ulang oleh rekonsiliasi memakai judul tanpa nama/NIM.
- Tabel `users` belum punya constraint unik pada NIM, jadi NIM ganda belum ditolak database, dan mahasiswa masih bisa mengubah NIM-nya kapan saja (perlu migrasi, belum diterapkan; butuh persetujuan).
- Hasil review keamanan yang butuh migrasi dan belum diterapkan: hak kolom `google_calendar_id`/`google_event_id` pada `appointments` tidak ada di migrasi (cocokkan dengan database langsung), kekuatan secret fungsi `anon` (minimal 32 karakter) belum dipaksa database, dan logout belum mencabut sesi jika cookie akses sudah kedaluwarsa.
- Penghapusan event di Google Calendar terlihat di aplikasi dalam kira-kira 35 detik selama pemilik membuka halaman My bookings (halaman memeriksa ulang otomatis selama tab terlihat; ada jeda 30 detik per mahasiswa di server), atau saat halaman dibuka/dimuat ulang, atau saat cron harian jalan; slot yang dibebaskan tidak langsung terlihat oleh mahasiswa lain. Notifikasi push Google Calendar akan memperbaikinya dan belum dibuat.
- Daftar bookings disimpan di cache sesi browser (valid 1 menit); cache dibuang setiap booking dibuat atau diubah.
- Tombol Update (reschedule) sudah ada di antarmuka dan diuji dengan data tiruan, tetapi belum dijalankan ke Supabase/Calendar sungguhan.
- Struktur backend baru (`backend/ARCHITECTURE.md`) hanya diverifikasi oleh unit test dan pengecekan rute; jalur rekonsiliasi (legacy, sync, replacement) belum punya unit test.
- Skenario booking, cancel, dan batas 3 booking belum dijalankan ke Supabase dan Google Calendar sungguhan.
- Video demo (`demo.mp4`) belum direkam.

## Risiko keamanan yang diketahui (hasil audit, belum diperbaiki)

Hasil audit manual (review kode, fuzzing 4.500+ request, pengujian dari luar terhadap situs produksi). Tidak ada pemindai exploit otomatis (Strix) yang dijalankan.

- **Satu kredensial service account menulis ke kedua kalender ruangan.** Mahasiswa tidak lagi memegang akses Calendar, tetapi jika kunci `GOOGLE_SERVICE_ACCOUNT_JSON` bocor, penyerang bisa mengubah event di kedua kalender itu (hanya itu). Putar kunci jika dicurigai bocor.
- **NIM tidak diverifikasi terhadap email.** Mahasiswa bisa mengisi/mengubah NIM-nya sendiri, termasuk NIM orang lain yang belum terdaftar (NIM unik sudah dipaksa database).
- **Rate limit hanya untuk `/api/v1/auth/` dan `/api/v1/google-auth/`** (paket Hobby hanya mengizinkan satu aturan). Endpoint booking tidak dibatasi; pemeriksaan Google (`verify=true`) dibatasi per instance saja, jadi pengguna jahat bisa memperbanyak panggilan ke kuota Google.
- **Insert langsung ke Supabase** dengan kunci publik bisa menahan satu slot ekstra (maksimal 4 baris aktif) sampai cron harian membersihkannya.
- Jika pembatalan sebuah reschedule gagal tepat setelah event lama dihapus, mahasiswa bisa kehilangan kedua booking (sangat jarang).
- Pembaruan otomatis My bookings (setiap ~35 detik) membuat satu permintaan per tab terbuka; belum ada koordinasi antar tab.
- **Login lain di Supabase:** metode login Email di Supabase aktif dan pendaftaran terbuka. Matikan (Authentication > Sign In / Providers > Email) agar satu-satunya jalan masuk adalah Google (yang memeriksa domain, `hd` dan izin Calendar).
- **Email kampus yang dipakai ulang** bisa mewarisi akun lama jika Supabase otomatis menautkan identitas; belum ada pengikatan ke `sub` Google (perlu kolom baru + migrasi).
- **Pengguna yang dikeluarkan dari Workspace** tetap punya sesi sampai 30 hari (sesi diperpanjang setiap refresh); batasi masa sesi di Supabase jika paketnya mendukung.
- **Kalender ruangan harus dibagikan** ke semua mahasiswa dengan izin "Make changes to events"; jika tidak, booking gagal dengan pesan yang meminta pemilik membagikan kalendernya.

Link video demo: https://drive.google.com/drive/folders/1w3qJziggvK4wHWlg2-z_DbvWK-4eC_5x?usp=drive_link

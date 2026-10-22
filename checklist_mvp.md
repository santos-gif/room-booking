# Checklist MVP — Discussion Room Booking

Terakhir dijalankan: 2026-10-21.

## Ringkasan pengujian

| Pemeriksaan | Hasil |
|---|---|
| Unit test backend (`pytest`, 14 file, 55 test) | PASSED 55/55 |
| Unit test frontend (`ng test`, 15 file, 51 test) | PASSED 51/51 |
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
| Token Google kedaluwarsa | Tombol "Reconnect Google Calendar" | Kode saja, belum diuji langsung |

## Keterbatasan yang diketahui

- Aturan 5 menit (slot tidak bisa dipesan kurang dari 5 menit sebelum mulai) hanya dijaga di backend; database belum menolaknya. Judul event Calendar `Discussion Room {1/2}-{Nama} ({NIM})` berlaku untuk booking baru dan update; event yang dibuat ulang oleh rekonsiliasi memakai judul tanpa nama/NIM.
- Tabel `users` belum punya constraint unik pada NIM, jadi NIM ganda belum ditolak database (perlu migrasi, belum diterapkan).
- Tombol Update (reschedule) sudah ada di antarmuka dan diuji dengan data tiruan, tetapi belum dijalankan ke Supabase/Calendar sungguhan.
- Struktur backend baru (`backend/ARCHITECTURE.md`) hanya diverifikasi oleh unit test dan pengecekan rute; jalur rekonsiliasi (legacy, sync, replacement) belum punya unit test.
- Skenario booking, cancel, dan batas 3 booking belum dijalankan ke Supabase dan Google Calendar sungguhan.
- Video demo (`demo.mp4`) belum direkam.

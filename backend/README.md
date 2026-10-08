# Discussion Room Booking

The Angular frontend talks only to the FastAPI API. The backend validates the
Google OAuth identity, issues HttpOnly session cookies, owns user/profile access,
reserves appointments in Supabase, and synchronizes room events with Google
Calendar. Supabase's service key and Google credentials must stay server-side.
API contracts live with their API feature; database record models are separate
under `app/models/`.

## Configure the backend

Copy `.env.example` to `.env.local` for local development and fill in the
server-side values. Configure the same variables in Vercel for deployment:

- `SUPABASE_URL` and `SUPABASE_KEY`: the project URL and server-only service
  role/secret key.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`: a
  Google OAuth Web client and its callback URL.
- `GOOGLE_CALENDAR_ROOM_1_ID` and `GOOGLE_CALENDAR_ROOM_2_ID`: the two room
  calendars. The OAuth user must have permission to create, update, and delete
  events in both calendars.
- `GOOGLE_TOKEN_ENCRYPTION_KEY`: a persistent Fernet key used to encrypt
  refresh tokens at rest. Changing it makes existing tokens unreadable.
- `SECRET_ACCESS_TOKEN_JWT_KEY` and `SECRET_REFRESH_TOKEN_JWT_KEY`: distinct
  random secrets of at least 32 characters. The app refuses to start if either
  is missing, too short, or identical to the other.
- `CRON_SECRET`: a strong random secret used to authorize Vercel's daily
  calendar reconciliation request. It must be at least 32 characters; Vercel
  sends it in the `Authorization: Bearer <CRON_SECRET>` header. The app refuses
  to start if it is missing or too short.
- `CORS_ORIGINS` and `FRONTEND_URL`: exact browser origin(s) and frontend URL.

Generate a Fernet key with:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For local HTTP development set `COOKIE_SECURE=false`. Production must use
HTTPS and `COOKIE_SECURE=true`. Use `COOKIE_SAMESITE=none` only if frontend and
API are cross-site, and then keep secure cookies enabled. The Angular
`NG_APP_API_URL` should point to the API prefix, such as
`http://localhost:8000/api/v1`.

The ignored `client_secret.json` file is not read by the application. Supply
OAuth secrets through environment variables; do not commit the file.

The API validates its required Supabase and Google integration settings during
startup. `GOOGLE_CALENDAR_ID` is not used; configure both room-specific
calendar IDs instead.

## Apply the Supabase migration

Back up the database, review existing appointment rows for invalid times,
overlaps, and daily-limit violations, then apply
`../supabase/migrations/202610050001_booking_integrity.sql` in Supabase.
The migration keeps the existing `timestamptz` fields and adds:

- valid room, major, NIM, weekday/hour, and one-hour constraints;
- a PostgreSQL exclusion constraint preventing overlapping room reservations;
- a transaction-serialized limit of two active one-hour appointments per user
  and Jakarta date, across both rooms;
- Google Calendar event/sync fields and safe reschedule tracking.

The migration intentionally removes existing RLS policies and revokes direct
`anon`/`authenticated` access to `users`, `appointments`, and
`google_refresh_tokens`. The app uses its own HttpOnly-cookie session rather
than Supabase Auth, so browser roles cannot safely express the app's ownership
rules. All table access must go through the authenticated backend. Never put
`SUPABASE_KEY` in the frontend.

The migration fails rather than silently changing data if existing users have
more than two active appointments on a Jakarta date, case-insensitive duplicate
user emails exist, or the new constraints are violated. Resolve those rows
explicitly and rerun the migration.

## OAuth and booking behavior

Add this exact callback URI to the Google OAuth client:

`https://discussion-room-booking-pita.vercel.app/api/v1/google-auth/oauth2callback`

Set `GOOGLE_REDIRECT_URI` to the deployment callback URL; use the local URL
`http://localhost:8000/api/v1/google-auth/oauth2callback` for development.
Google's verified email must end in exactly `@student.pradita.ac.id` or
`@pradita.ac.id`. First-time users are created from that verified identity and
must complete onboarding before booking.

Bookings are one hour and start on weekdays from 08:00 through 16:00 WIB, so the
last slot ends at 17:00. Each user may hold at most two active reservations per
Jakarta calendar day. The backend and database both enforce these rules.
Timestamp inputs and displays use `Asia/Jakarta`; Supabase stores UTC instants
in the existing `timestamptz` fields.

Booking records are reserved as `pending` before Google Calendar is called.
If Calendar is temporarily unavailable, the reservation remains pending and
continues to hold its slot until reconciliation succeeds or an authorized
cancellation completes. Calendar events use a stable event ID for retries.
Cancellation removes the Google event before releasing the database slot.
Rescheduling reserves and syncs the replacement before cancelling the old
booking; if the old cancellation fails, the new reservation is compensated
where possible and the original remains.

Vercel calls `/api/v1/appointments/reconcile` daily at 00:10 UTC (07:10 WIB).
It retries pending events, releases bookings whose events were deleted
externally, and restores event times changed directly in Google Calendar. The
endpoint requires the configured Vercel `Authorization: Bearer <CRON_SECRET>` header. This is eventual
reconciliation, not an immediate push notification; configure a more frequent
schedule only if the Vercel plan supports it. While the booking screen remains
open, it refreshes availability every 30 seconds; the database constraints
remain authoritative if polling is delayed.

## Run locally

From `backend`:

```powershell
python -m pip install -e .
uvicorn app.main:app --reload
```

From `frontend`:

```powershell
npm install
npm start
```

## MVP verification

Run the unit/contract tests from `backend`:

```powershell
python -m unittest discover -s tests -v
```

These tests verify booking validation, timezone serialization, OAuth URL
configuration, and credential/error handling without contacting external
services. For a real demonstration, configure the environment above, apply the
booking migration to a non-production Supabase project, and run the app.
Sign in through Google in the browser, submit a booking, then verify the
appointment row in Supabase and the corresponding event in the selected room
calendar. Do not report those external steps as verified until they have been
observed against the real services.

The app currently uses Calendar reads and scheduled reconciliation. It does
not register Google Calendar watch channels or webhooks.

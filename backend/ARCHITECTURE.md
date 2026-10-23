# Backend map

FastAPI app. Everything lives in `app/`. Plain functions in named files, no classes to learn.

## The tree

```
app/
  main.py          builds the FastAPI app, CORS, CSRF check, database-error handler
  config.py        settings read from .env, plus startup checks
  database.py      Supabase client factory (create_supabase_client) and the FastAPI dependencies
  cookies.py       EVERY cookie name, and the functions that set or clear them
  models/          pydantic shapes of database rows
  google_api/      the only code that talks to Google
    oauth.py         scopes, create_flow (login URL / code exchange), verify_google_identity
    credentials.py   builds Google credentials for a user, refreshing the access token
    calendar_api.py  room_calendar_id, calendar service builder, create event, list events
    calendar_single_event.py  update / delete / get one event
    token_crypto.py  encrypt / decrypt the stored refresh token
    exceptions.py    Google* errors (HTTP status + message)
    types.py         GoogleIdentity, GoogleCalendarEvent
  queries/         the Supabase table/RPC calls for Google tokens and appointments
    google_tokens.py load / store / invalidate the refresh token
    appointments.py  list, get, insert, state updates, availability, reconciliation RPCs
  api/v1/
    api_router.py    mounts the three routers below
    auth/            router.py, helper.py (current user, renew tokens, onboarding), revoke.py (end a
                     session on Supabase's side at logout), types, exceptions
    google_auth/     router.py (routes only), login.py (start login), then the finish-login steps:
      callback.py          the order of steps; every refusal becomes a redirect with a fixed code
      callback_identity.py who may sign in (domain, verified email, Workspace claim), SignInRefused
      callback_profile.py  Supabase session, profile, and the stored Google refresh token
    appointment/     router.py, types.py, exceptions.py, plus:
      slots.py         slot rules (hours, lead, 90-day window), availability, response shapes
      booking_date.py  the availability `date` parameter, checked where input enters
      calendar_event.py   title and body of a booking's Google event
      booking.py       list a student's bookings; create one (reserve, event, confirm)
      booking_event.py create the Google event, or roll the reservation back
      rollback.py      discard or mark failed a pending booking
      cancel.py        cancel a booking (its event, then the row, deleted straight away)
      reschedule.py    move a booking (create new, cancel old)
      reconcile.py     cron job: fix bookings that disagree with Google Calendar
      reconcile_sync.py          one booking vs its calendar event
      reconcile_replacements.py  cancel the old booking after a confirmed reschedule
      verify.py        GET /?verify=true: drop bookings whose Google event was deleted, fix old titles
```

## The one-way import rule

```
routers -> service files -> google_api / queries -> config, models, database
```

`cookies.py` imports only `config`. A file may import things to its right, never to its
left. If you need something from the left, pass it in as an argument instead.
Tests patch a name where it is *used* (e.g. `booking.create_calendar_event`).

## I want to change... -> look in...

| I want to change...                         | look in...                                             |
|---------------------------------------------|--------------------------------------------------------|
| how login works                             | `api/v1/google_auth/login.py` and `callback.py`        |
| the raw Google calls (login, id token)      | `google_api/oauth.py`                                  |
| which emails may sign in                    | `api/v1/google_auth/callback_identity.py`              |
| a cookie name, lifetime or flags            | `cookies.py`                                           |
| how Google calendar events are created      | `google_api/calendar_api.py`                           |
| which calendar a room uses                  | `google_api/calendar_api.py` (`room_calendar_id`)      |
| how the Google token is stored / refreshed  | `queries/google_tokens.py`, `google_api/credentials.py`|
| booking hours, weekdays, max 3, 5-min lead  | `api/v1/appointment/slots.py`                          |
| what happens when a booking fails midway    | `appointment/booking_event.py`, `rollback.py`          |
| what a booking looks like in Google Calendar| `appointment/calendar_event.py`                        |
| what logout really revokes                  | `api/v1/auth/revoke.py`                                |
| cancelling or rescheduling                  | `cancel.py`, `reschedule.py` in `appointment/`         |
| the nightly repair job                      | `appointment/reconcile*.py`                            |
| deleted-in-Google bookings on My bookings   | `appointment/verify.py`                                |
| any Supabase query on appointments          | `queries/appointments.py`                              |
| an HTTP route path or its inputs            | the `router.py` of that feature                        |
| the CSRF check                              | `main.py`                                              |

## Known leftovers (on purpose, for later)

- `google_api/credentials.py` still takes `response` and sets the refreshed-token cookie.
  That is an exception to "google_api builds no HTTP responses". It also reads the token
  through `queries/google_tokens.py`, so google_api and queries import each other's level.
- Some Supabase queries still live outside `queries/` (users table in `auth/helper.py` and
  `callback_profile.py`).
- Reconcile has only `booker_id`, no name or NIM, and there is no migration for it. A recreated
  event is titled `Discussion Room {n}`; updating an existing event keeps its current title.
- The 5-minute lead rule and the 90-day window are mirrored by the database trigger
  `appointments_booking_window`; keep `slots.py` (`LEAD`, `MAX_ADVANCE`) and the trigger in step.
- Students write to the room calendars with their own Google token, so a hostile student could
  delete others' events through Google's API. The real fix is one service credential (not built).
- The catch-all 500 handler in `main.py` is served outside `CORSMiddleware`, so a browser may
  not see CORS headers on that response.
- `GET /api/v1/appointments/?verify=true` checks up to 10 upcoming *confirmed* bookings of the
  caller against Google (8 s budget). A 404/410 or `cancelled` event moves the row to cancelled
  through `update_own_appointment_state`, but a 404/410 only counts as "gone" if
  `calendar_is_reachable` (calendars.get) confirms the room calendar is still readable by that
  user; an unreachable calendar (403/404/410) keeps the row and logs a warning. A wrong title is
  healed; any other failure keeps the row. Each user is verified at most once per 30 s
  (in-memory, per instance, so it limits bursts, not globally); inside that window the plain list
  is returned with no Google call. The cron secret check lives in `reconcile.py`
  (`require_cron_secret`, compares bytes so a non-ASCII header is a 401).
  Limitation: nothing is pushed. Other students only see a slot freed by a Calendar-side delete
  after the owner opens My bookings (verify) or the daily cron runs. Google Calendar push
  notifications (events.watch) would fix that and were not built.
- Unmapped insert errors still become the generic 500 storage error (only 23P01, 23505, P0001 and,
  for reschedules, 23514/23503 are mapped).

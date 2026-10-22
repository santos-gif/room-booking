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
    auth/            router.py, helper.py (current user, renew tokens, onboarding), types, exceptions
    google_auth/     router.py (routes only), login.py (start login), callback.py (finish login)
    appointment/     router.py, types.py, exceptions.py, plus:
      slots.py         slot rules, availability, response shapes
      booking.py       list and create a booking
      cancel.py        cancel a booking (and find one of your own)
      reschedule.py    move a booking (create new, cancel old)
      reconcile.py     cron job: fix bookings that disagree with Google Calendar
      reconcile_sync.py          one booking vs its calendar event
      reconcile_replacements.py  cancel the old booking after a confirmed reschedule
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
| which emails may sign in                    | `api/v1/google_auth/callback.py` (`_is_allowed_email`) |
| a cookie name, lifetime or flags            | `cookies.py`                                           |
| how Google calendar events are created      | `google_api/calendar_api.py`                           |
| which calendar a room uses                  | `google_api/calendar_api.py` (`room_calendar_id`)      |
| how the Google token is stored / refreshed  | `queries/google_tokens.py`, `google_api/credentials.py`|
| booking hours, weekdays, max 3, 5-min lead  | `api/v1/appointment/slots.py`                          |
| what happens when a booking fails midway    | `api/v1/appointment/booking.py`                        |
| cancelling or rescheduling                  | `cancel.py`, `reschedule.py` in `appointment/`         |
| the nightly repair job                      | `appointment/reconcile*.py`                            |
| any Supabase query on appointments          | `queries/appointments.py`                              |
| an HTTP route path or its inputs            | the `router.py` of that feature                        |
| the CSRF check                              | `main.py`                                              |

## Known leftovers (on purpose, for later)

- `google_api/credentials.py` still takes `response` and sets the refreshed-token cookie.
  That is an exception to "google_api builds no HTTP responses". It also reads the token
  through `queries/google_tokens.py`, so google_api and queries import each other's level.
- `complete_google_oauth` in `callback.py` keeps a test-only branch that accepts a
  `Request` and a `Client` in place of `state` and `code`. Left alone as a separate follow-up.
- `callback.py` is about 160 lines and `appointment/router.py` is about 160 lines.
  They are over the 150-line goal; splitting `callback.py` would scatter one login flow.
- Some Supabase queries still live outside `queries/` (users table in `auth/helper.py` and
  `callback.py`, the profile RPC in `callback.py`).
- Reconcile has only `booker_id`, no name or NIM, and there is no migration for it. A recreated
  event is titled `Discussion Room {n}`; updating an existing event keeps its current title.
- The database itself does not enforce the 5-minute lead rule or reject past start times;
  only `slots.py` (`LEAD`) does. A direct database write could still book a past slot.
- `users.nim` has no unique constraint in `supabase/migrations`, so the duplicate-NIM 409 in
  `auth/helper.py` only fires once such a constraint exists.
- The catch-all 500 handler in `main.py` is served outside `CORSMiddleware`, so a browser may
  not see CORS headers on that response.

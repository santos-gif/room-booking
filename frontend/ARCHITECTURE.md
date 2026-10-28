# Frontend map

Angular 22, standalone components, signals. Everything lives in `src/app`.

## The three top-level folders

| Folder | What goes here | Rule |
|--------|----------------|------|
| `core/` | The essential code for talking to the server, and the security around it: route guards, HTTP interceptors, the global error handler, app-wide services (such as the navigation lock), the types of server data, and `utils/`. Pipes will live here too (none yet). | Features may use `core/`. `core/` may use `shared/`. `core/` never imports from a feature. |
| `shared/` | Utilities that span features, mainly: reusable components (header, dialogs), helpers, and directives (none yet). The broader layer. | No server calls. Never imports from a feature. |
| `features/<name>/` | One folder per feature. A feature is centred on one page. | A feature never imports from another feature. |

`core/` and `shared/` both span every feature. The difference is importance: `core/` is what the app
cannot talk to the server (or stay safe) without; `shared/` is convenience that several features reuse.

## Inside a feature

```
features/booking-form/
  page/        the screen the router opens: holds the state, wires everything together
  components/  pieces that modularise the page; each in its own folder (ts + html + css + spec)
  service/     what this feature may reach on the server (which endpoints); one service per feature
  helpers/     plain-function logic split out when the page or service grows too large
  types/       types used only inside this feature
```

How the layers talk (always downwards, never skipping):

```
page  ->  feature service  ->  core service / HTTP
page  ->  components        (inputs go down, events come up; components never call a service)
page  ->  helpers           (functions the page calls while it is being built)
```

Why this shape: a component you can read in one screen is easy to change; keeping server access in
one service per feature means a rule such as "saving your profile must refresh the cached user" is
written once, not in every page.

## Small rules

- File names are kebab-case: `booking-form-page.ts`, `.html`, `.css`, `.spec.ts` side by side.
- One component per folder. A test sits next to the file it tests.
- A feature service is provided by its page (`providers: [XService]`), so it lives and dies with
  the page. Services in `core/services` are `providedIn: 'root'`: one copy for the whole app.
- Feature and shared logic helpers go in `helpers/`; `utils/` exists only in `core` (see below).
- Every file stays under 150 lines and 150 columns.

## Where things are today

| Feature | Has |
|---------|-----|
| `login` | `page`, `components`, `service` |
| `onboarding` | `page`, `components`, `service`, `types` (also serves `/profile`, the same screen in "edit" mode) |
| `booking-form` | `page`, `components`, `service`, `helpers`, `types` |
| `my-bookings` | `page`, `components`, `service` (a read-only filter over the shared `core/services/bookings-store.ts`) |
| `staff` | `page`, `components` (closures, override), `service`, `types` (route `/staff`, guarded by `staffGuard`; the server is the real check) |
| `access-denied` | `page` (a static message page, no server access) |

## `utils` and `helpers` are different things

- **`core/utils/`** holds the small functions a major file in `core` cannot work without:
  `cookies.ts` (the CSRF cookie the interceptors send) and `api-failure.ts` (the shape of a server
  error). If one of these is wrong, talking to the server breaks.
- **`helpers/`** (in a feature, or in `shared/`) only modularises logic: they split bits and pieces
  out of a page, a service, or even a core file, but they never replace what `core/utils` provides.
  Today `shared/helpers/` holds `jakarta-today.ts` (dates in Jakarta time), `visible-timer.ts`
  (a timer that pauses in hidden tabs) and `dialog-width.ts`.

## `core` may use `shared`

`shared` is the broader layer, so `core` is allowed to use its components: the global error handler
and the server-error interceptor open `shared/components/error-dialog` and use
`shared/helpers/dialog-width`. The one rule that never bends is that nothing in `core` or `shared`
imports from a feature.

## Changing the structure

Moving, merging, renaming or deleting files that carry this pattern is decided by the owner. The
user-level skill `code-structure-guard` (in `~/.claude/skills`, so it works in every project) makes the assistant propose first (what, where, why, an alternative)
and wait for a yes.

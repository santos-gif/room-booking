# `supabase_auth_booking_rules.sql`

```sql
BEGIN;

-- ============================================================
-- 1. Extensions
-- ============================================================

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ============================================================
-- 2. Connect application profiles to Supabase Auth
-- ============================================================

-- Existing profile IDs must already belong to Supabase Auth users.
-- Stop safely rather than attaching the wrong identities.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.users AS u
        LEFT JOIN auth.users AS au ON au.id = u.id
        WHERE au.id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Some public.users IDs do not exist in auth.users. Resolve these profiles before applying this migration.';
    END IF;
END;
$$;

ALTER TABLE public.users
    ALTER COLUMN id DROP DEFAULT,
    ALTER COLUMN nim DROP NOT NULL,
    ALTER COLUMN major DROP NOT NULL,
    ALTER COLUMN email SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.users'::regclass
          AND conname = 'users_id_auth_user_fkey'
    ) THEN
        ALTER TABLE public.users
            ADD CONSTRAINT users_id_auth_user_fkey
            FOREIGN KEY (id)
            REFERENCES auth.users(id)
            ON DELETE CASCADE;
    END IF;
END;
$$;

-- ============================================================
-- 3. Automatically create profiles at signup
-- ============================================================

CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    -- Only university accounts are eligible for application profiles.
    IF split_part(lower(NEW.email), '@', 2) NOT IN (
        'student.pradita.ac.id',
        'pradita.ac.id'
    ) THEN
        RETURN NEW;
    END IF;

    INSERT INTO public.users (id, email, name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(
            NULLIF(NEW.raw_user_meta_data ->> 'full_name', ''),
            NULLIF(NEW.raw_user_meta_data ->> 'name', ''),
            split_part(NEW.email, '@', 1)
        )
    )
    ON CONFLICT (id) DO NOTHING;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION public.handle_new_auth_user();

-- Create profiles for existing eligible Auth accounts too.
INSERT INTO public.users (id, email, name)
SELECT
    au.id,
    au.email,
    COALESCE(
        NULLIF(au.raw_user_meta_data ->> 'full_name', ''),
        NULLIF(au.raw_user_meta_data ->> 'name', ''),
        split_part(au.email, '@', 1)
    )
FROM auth.users AS au
WHERE au.email IS NOT NULL
  AND split_part(lower(au.email), '@', 2) IN (
      'student.pradita.ac.id',
      'pradita.ac.id'
  )
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 4. Appointment rules
-- ============================================================

ALTER TABLE public.appointments
    ADD COLUMN IF NOT EXISTS google_calendar_id text,
    ADD COLUMN IF NOT EXISTS google_event_id text,
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'confirmed',
    ADD COLUMN IF NOT EXISTS sync_status text NOT NULL DEFAULT 'legacy';

-- Replace the old unconditional room-overlap constraint.
ALTER TABLE public.appointments
    DROP CONSTRAINT IF EXISTS exclude_room_overlaps;

ALTER TABLE public.appointments
    DROP CONSTRAINT IF EXISTS appointments_room_time_no_overlap;

ALTER TABLE public.appointments
    ADD CONSTRAINT appointments_room_time_no_overlap
    EXCLUDE USING gist (
        room_number WITH =,
        tstzrange(start_time, end_time, '[)') WITH &&
    )
    WHERE (status IN ('pending', 'confirmed'));

-- Add booking validation constraints only if absent.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.appointments'::regclass
          AND conname = 'appointments_room_allowed'
    ) THEN
        ALTER TABLE public.appointments
            ADD CONSTRAINT appointments_room_allowed
            CHECK (room_number IN (1, 2));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.appointments'::regclass
          AND conname = 'appointments_one_hour'
    ) THEN
        ALTER TABLE public.appointments
            ADD CONSTRAINT appointments_one_hour
            CHECK (
                start_time < end_time
                AND end_time - start_time = interval '1 hour'
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.appointments'::regclass
          AND conname = 'appointments_status_allowed'
    ) THEN
        ALTER TABLE public.appointments
            ADD CONSTRAINT appointments_status_allowed
            CHECK (status IN ('pending', 'confirmed', 'cancelled'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.appointments'::regclass
          AND conname = 'appointments_sync_status_allowed'
    ) THEN
        ALTER TABLE public.appointments
            ADD CONSTRAINT appointments_sync_status_allowed
            CHECK (
                sync_status IN ('pending', 'synced', 'failed', 'legacy')
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.appointments'::regclass
          AND conname = 'appointments_weekday_hours'
    ) THEN
        ALTER TABLE public.appointments
            ADD CONSTRAINT appointments_weekday_hours
            CHECK (
                EXTRACT(
                    ISODOW FROM start_time AT TIME ZONE 'Asia/Jakarta'
                ) BETWEEN 1 AND 5
                AND (start_time AT TIME ZONE 'Asia/Jakarta')::time
                    >= TIME '08:00'
                AND (start_time AT TIME ZONE 'Asia/Jakarta')::time
                    < TIME '17:00'
                AND (end_time AT TIME ZONE 'Asia/Jakarta')::time
                    <= TIME '17:00'
                AND (start_time AT TIME ZONE 'Asia/Jakarta')::time
                    = date_trunc(
                        'hour',
                        start_time AT TIME ZONE 'Asia/Jakarta'
                    )::time
            );
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS appointments_booker_day_idx
ON public.appointments (
    booker_id,
    ((start_time AT TIME ZONE 'Asia/Jakarta')::date)
)
WHERE status IN ('pending', 'confirmed');

CREATE UNIQUE INDEX IF NOT EXISTS appointments_google_event_uidx
ON public.appointments (google_calendar_id, google_event_id)
WHERE google_calendar_id IS NOT NULL
  AND google_event_id IS NOT NULL;

-- ============================================================
-- 5. Maximum two active bookings per user per Jakarta day
-- ============================================================

CREATE OR REPLACE FUNCTION public.enforce_daily_booking_limit()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
DECLARE
    active_count integer;
    booking_day date;
BEGIN
    IF NEW.status NOT IN ('pending', 'confirmed') THEN
        RETURN NEW;
    END IF;

    booking_day :=
        (NEW.start_time AT TIME ZONE 'Asia/Jakarta')::date;

    -- Serialize booking-limit checks for the same user.
    PERFORM 1
    FROM public.users
    WHERE id = NEW.booker_id
    FOR UPDATE;

    SELECT count(*)
    INTO active_count
    FROM public.appointments AS a
    WHERE a.booker_id = NEW.booker_id
      AND a.status IN ('pending', 'confirmed')
      AND (a.start_time AT TIME ZONE 'Asia/Jakarta')::date = booking_day
      AND a.id <> NEW.id;

    IF active_count >= 2 THEN
        RAISE EXCEPTION
            'A user may have at most two active bookings per day';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS appointments_daily_booking_limit
ON public.appointments;

CREATE TRIGGER appointments_daily_booking_limit
BEFORE INSERT OR UPDATE OF booker_id, start_time, status
ON public.appointments
FOR EACH ROW
EXECUTE FUNCTION public.enforce_daily_booking_limit();

-- ============================================================
-- 6. Row-level security and browser permissions
-- ============================================================

-- Remove existing policies so old permissive policies cannot
-- accidentally override the intended access rules.
DO $$
DECLARE
    p record;
BEGIN
    FOR p IN
        SELECT schemaname, tablename, policyname
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename IN (
              'users',
              'appointments',
              'google_refresh_tokens'
          )
    LOOP
        EXECUTE format(
            'DROP POLICY %I ON %I.%I',
            p.policyname,
            p.schemaname,
            p.tablename
        );
    END LOOP;
END;
$$;

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.google_refresh_tokens ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE
    public.users,
    public.appointments,
    public.google_refresh_tokens
FROM anon, authenticated;

-- Users can view their own profile.
GRANT SELECT ON public.users TO authenticated;

CREATE POLICY users_select_own
ON public.users
FOR SELECT
TO authenticated
USING (id = (SELECT auth.uid()));

-- Users can edit only their own onboarding fields.
GRANT UPDATE (nim, major) ON public.users TO authenticated;

CREATE POLICY users_update_own
ON public.users
FOR UPDATE
TO authenticated
USING (id = (SELECT auth.uid()))
WITH CHECK (id = (SELECT auth.uid()));

-- Users can view only their own appointments.
-- Booking creation, updates, and cancellations go through FastAPI.
GRANT SELECT ON public.appointments TO authenticated;

CREATE POLICY appointments_select_own
ON public.appointments
FOR SELECT
TO authenticated
USING (booker_id = (SELECT auth.uid()));

-- Refresh tokens must never be directly accessible from the browser.
-- FastAPI should access them using its server-side credentials.

COMMIT;
```

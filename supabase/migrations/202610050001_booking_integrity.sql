BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ============================================================
-- 1. User constraints
-- ============================================================

ALTER TABLE public.users
    ALTER COLUMN email SET NOT NULL;

ALTER TABLE public.users
    ADD CONSTRAINT users_nim_positive
        CHECK (nim IS NULL OR nim > 0),
    ADD CONSTRAINT users_major_allowed
        CHECK (
            major IS NULL OR major IN (
                'IT',
                'Management',
                'Culinary Arts',
                'Visual Communication Design',
                'Accounting',
                'Architecture',
                'Business Information System',
                'Civil Engineering',
                'Hospitality & Tourism',
                'Interior Design',
                'Urban Planning'
            )
        );

CREATE UNIQUE INDEX users_email_case_insensitive_uidx
    ON public.users (lower(email));

-- ============================================================
-- 2. Appointment columns and constraints
-- ============================================================

ALTER TABLE public.appointments
    ALTER COLUMN booker_id SET NOT NULL,
    ALTER COLUMN room_number SET NOT NULL,
    ALTER COLUMN start_time SET NOT NULL,
    ALTER COLUMN end_time SET NOT NULL;

ALTER TABLE public.appointments
    ADD COLUMN google_calendar_id text,
    ADD COLUMN google_event_id text,
    ADD COLUMN replaces_appointment_id uuid
        REFERENCES public.appointments(id),
    ADD COLUMN status text NOT NULL DEFAULT 'confirmed',
    ADD COLUMN sync_status text NOT NULL DEFAULT 'legacy',
    ADD CONSTRAINT appointments_room_allowed
        CHECK (room_number IN (1, 2)),
    ADD CONSTRAINT appointments_one_hour
        CHECK (
            start_time < end_time
            AND end_time - start_time = interval '1 hour'
        ),
    ADD CONSTRAINT appointments_status_allowed
        CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    ADD CONSTRAINT appointments_sync_status_allowed
        CHECK (sync_status IN ('pending', 'synced', 'failed', 'legacy')),
    ADD CONSTRAINT appointments_weekday_hours
        CHECK (
            EXTRACT(
                ISODOW FROM start_time AT TIME ZONE 'Asia/Jakarta'
            ) BETWEEN 1 AND 5
            AND EXTRACT(
                HOUR FROM start_time AT TIME ZONE 'Asia/Jakarta'
            ) BETWEEN 8 AND 16
            AND EXTRACT(
                MINUTE FROM start_time AT TIME ZONE 'Asia/Jakarta'
            ) = 0
            AND EXTRACT(
                SECOND FROM start_time AT TIME ZONE 'Asia/Jakarta'
            ) = 0
        );

-- Refuse migration if existing active bookings violate the daily limit.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.appointments
        WHERE status IN ('pending', 'confirmed')
        GROUP BY
            booker_id,
            (start_time AT TIME ZONE 'Asia/Jakarta')::date
        HAVING count(*) > 2
    ) THEN
        RAISE EXCEPTION
            'Resolve existing users with more than two active daily bookings before migrating';
    END IF;
END;
$$;

-- Replace the old unconditional exclusion constraint.
-- This must happen in the first migration, before adding the new one.
ALTER TABLE public.appointments
    DROP CONSTRAINT IF EXISTS exclude_room_overlaps;

ALTER TABLE public.appointments
    ADD CONSTRAINT appointments_room_time_no_overlap
    EXCLUDE USING gist (
        room_number WITH =,
        tstzrange(start_time, end_time, '[)') WITH &&
    )
    WHERE (status IN ('pending', 'confirmed'));

-- ============================================================
-- 3. Appointment indexes
-- ============================================================

CREATE UNIQUE INDEX appointments_google_event_uidx
    ON public.appointments (google_calendar_id, google_event_id)
    WHERE google_calendar_id IS NOT NULL
      AND google_event_id IS NOT NULL;

CREATE INDEX appointments_booker_day_idx
    ON public.appointments (
        booker_id,
        ((start_time AT TIME ZONE 'Asia/Jakarta')::date)
    )
    WHERE status IN ('pending', 'confirmed');

CREATE UNIQUE INDEX appointments_single_active_replacement_uidx
    ON public.appointments (replaces_appointment_id)
    WHERE replaces_appointment_id IS NOT NULL
      AND status IN ('pending', 'confirmed');

-- ============================================================
-- 4. Daily booking limit
-- ============================================================

CREATE OR REPLACE FUNCTION public.enforce_daily_user_booking_limit()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
    booking_date date;
    active_count integer;
BEGIN
    IF NEW.status NOT IN ('pending', 'confirmed') THEN
        RETURN NEW;
    END IF;

    IF NEW.replaces_appointment_id IS NOT NULL
       AND NOT EXISTS (
            SELECT 1
            FROM public.appointments AS replaced
            WHERE replaced.id = NEW.replaces_appointment_id
              AND replaced.booker_id = NEW.booker_id
              AND replaced.status IN ('pending', 'confirmed')
       )
    THEN
        RAISE EXCEPTION
            'Replacement must refer to an active appointment of the same user'
            USING ERRCODE = '23514';
    END IF;

    booking_date :=
        (NEW.start_time AT TIME ZONE 'Asia/Jakarta')::date;

    -- Serialize booking-limit checks for the same user.
    PERFORM id
    FROM public.users
    WHERE id = NEW.booker_id
    FOR UPDATE;

    SELECT count(*)
    INTO active_count
    FROM public.appointments
    WHERE booker_id = NEW.booker_id
      AND (start_time AT TIME ZONE 'Asia/Jakarta')::date = booking_date
      AND status IN ('pending', 'confirmed')
      AND id <> NEW.id
      AND (
          NEW.replaces_appointment_id IS NULL
          OR id <> NEW.replaces_appointment_id
      );

    IF active_count >= 2 THEN
        RAISE EXCEPTION
            'A user may have at most two active bookings per day'
            USING ERRCODE = 'P0001';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS appointments_daily_user_booking_limit
    ON public.appointments;

CREATE TRIGGER appointments_daily_user_booking_limit
BEFORE INSERT OR UPDATE OF
    booker_id,
    start_time,
    status,
    replaces_appointment_id
ON public.appointments
FOR EACH ROW
EXECUTE FUNCTION public.enforce_daily_user_booking_limit();

-- ============================================================
-- 5. Remove old broad policies and direct browser table access
-- ============================================================

DO $$
DECLARE
    table_name text;
    policy_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'users',
        'appointments',
        'google_refresh_tokens'
    ]
    LOOP
        FOR policy_name IN
            SELECT policy.policyname
            FROM pg_policies AS policy
            WHERE policy.schemaname = 'public'
              AND policy.tablename = table_name
        LOOP
            EXECUTE format(
                'DROP POLICY %I ON public.%I',
                policy_name,
                table_name
            );
        END LOOP;
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

COMMIT;

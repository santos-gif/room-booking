BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ============================================================
-- 1. Supabase Auth identity mapping
-- ============================================================

ALTER TABLE public.users
    ALTER COLUMN id DROP DEFAULT,
    ALTER COLUMN email SET NOT NULL,
    ALTER COLUMN nim DROP NOT NULL,
    ALTER COLUMN major DROP NOT NULL;

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

-- The first migration creates these constraints and this index.
-- Do not create them a second time here.

-- ============================================================
-- 2. Private backend secret storage
-- ============================================================

CREATE SCHEMA IF NOT EXISTS private;

REVOKE ALL ON SCHEMA private FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS private.backend_secrets (
    name text PRIMARY KEY,
    secret_value text NOT NULL
);

REVOKE ALL ON TABLE private.backend_secrets
    FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION private.require_backend_secret(candidate text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, private
AS $$
BEGIN
    IF candidate IS NULL OR NOT EXISTS (
        SELECT 1
        FROM private.backend_secrets
        WHERE name = 'supabase_backend_rpc'
          AND secret_value = candidate
    ) THEN
        RAISE EXCEPTION 'Backend authorization required'
            USING ERRCODE = '42501';
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION private.require_backend_secret(text)
    FROM PUBLIC, anon, authenticated;

-- ============================================================
-- 3. Current user identity
-- ============================================================

CREATE OR REPLACE FUNCTION public.current_profile_id()
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
    SELECT auth.uid()::text
    WHERE EXISTS (
        SELECT 1
        FROM public.users
        WHERE id = auth.uid()
    );
$$;

CREATE OR REPLACE FUNCTION public.get_or_create_current_profile(
    profile_name text
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, auth
AS $$
DECLARE
    current_auth_user uuid := auth.uid();
    current_email text;
    current_name text;
    existing_profile_id public.users.id%TYPE;
BEGIN
    IF current_auth_user IS NULL THEN
        RAISE EXCEPTION 'Authenticated user required'
            USING ERRCODE = '42501';
    END IF;

    SELECT email
    INTO current_email
    FROM auth.users
    WHERE id = current_auth_user
      AND email_confirmed_at IS NOT NULL;

    IF current_email IS NULL
       OR split_part(lower(current_email), '@', 2) NOT IN (
            'student.pradita.ac.id',
            'pradita.ac.id'
       )
    THEN
        RAISE EXCEPTION 'A verified university email is required'
            USING ERRCODE = '42501';
    END IF;

    SELECT id
    INTO existing_profile_id
    FROM public.users
    WHERE id = current_auth_user;

    IF existing_profile_id IS NOT NULL THEN
        RETURN existing_profile_id::text;
    END IF;

    -- Never attach an existing profile based on email alone.
    IF EXISTS (
        SELECT 1
        FROM public.users
        WHERE lower(email) = lower(current_email)
    ) THEN
        RAISE EXCEPTION
            'An existing profile requires administrator identity linking'
            USING ERRCODE = 'P0001';
    END IF;

    current_name := nullif(btrim(profile_name), '');

    IF current_name IS NULL THEN
        current_name := split_part(current_email, '@', 1);
    END IF;

    BEGIN
        INSERT INTO public.users (id, email, name)
        VALUES (current_auth_user, current_email, current_name);
    EXCEPTION WHEN unique_violation THEN
        SELECT id
        INTO existing_profile_id
        FROM public.users
        WHERE id = current_auth_user;

        IF existing_profile_id IS NOT NULL THEN
            RETURN existing_profile_id::text;
        END IF;

        RAISE EXCEPTION
            'An existing profile requires administrator identity linking'
            USING ERRCODE = 'P0001';
    END;

    RETURN current_auth_user::text;
END;
$$;

-- ============================================================
-- 4. Booking availability
-- ============================================================

CREATE OR REPLACE FUNCTION public.get_booking_availability(
    booking_date date,
    requested_room integer,
    excluded_appointment_id uuid DEFAULT NULL
)
RETURNS TABLE (
    booked_starts timestamptz[],
    bookings_used bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    current_profile text := public.current_profile_id();
    day_start timestamptz;
BEGIN
    IF current_profile IS NULL THEN
        RAISE EXCEPTION 'Invalid availability request'
            USING ERRCODE = '42501';
    END IF;

    IF booking_date IS NULL
       OR requested_room IS NULL
       OR requested_room NOT IN (1, 2)
    THEN
        RAISE EXCEPTION 'Invalid availability request'
            USING ERRCODE = '22023';
    END IF;

    IF excluded_appointment_id IS NOT NULL
       AND NOT EXISTS (
            SELECT 1
            FROM public.appointments AS owned
            WHERE owned.id = excluded_appointment_id
              AND owned.booker_id::text = current_profile
              AND owned.status IN ('pending', 'confirmed')
       )
    THEN
        RAISE EXCEPTION 'Appointment access denied'
            USING ERRCODE = '42501';
    END IF;

    day_start := booking_date::timestamp AT TIME ZONE 'Asia/Jakarta';

    RETURN QUERY
    SELECT
        coalesce(
            array_agg(a.start_time)
                FILTER (WHERE a.room_number = requested_room),
            '{}'::timestamptz[]
        ),
        count(*) FILTER (
            WHERE a.booker_id::text = current_profile
        )
    FROM public.appointments AS a
    WHERE a.status IN ('pending', 'confirmed')
      AND a.start_time >= day_start
      AND a.start_time < day_start + interval '1 day'
      AND (
          excluded_appointment_id IS NULL
          OR a.id <> excluded_appointment_id
      );
END;
$$;

-- ============================================================
-- 5. Controlled appointment state transitions
-- ============================================================

CREATE OR REPLACE FUNCTION public.update_own_appointment_state(
    target_appointment_id uuid,
    new_status text,
    new_sync_status text
)
RETURNS SETOF public.appointments
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    current_profile text := public.current_profile_id();
    updated_appointment public.appointments;
BEGIN
    IF current_profile IS NULL THEN
        RAISE EXCEPTION 'Authenticated profile required'
            USING ERRCODE = '42501';
    END IF;

    IF NOT (
        (new_status = 'pending' AND new_sync_status = 'failed')
        OR (new_status = 'confirmed' AND new_sync_status = 'synced')
        OR (new_status = 'cancelled' AND new_sync_status = 'synced')
    ) THEN
        RAISE EXCEPTION 'Invalid appointment state transition'
            USING ERRCODE = '22023';
    END IF;

    UPDATE public.appointments AS appointment
    SET status = new_status,
        sync_status = new_sync_status
    WHERE appointment.id = target_appointment_id
      AND appointment.booker_id::text = current_profile
      AND (
          (
              new_status = 'pending'
              AND appointment.status = 'pending'
              AND appointment.sync_status = 'pending'
          )
          OR (
              new_status = 'confirmed'
              AND appointment.status = 'pending'
              AND appointment.sync_status IN ('pending', 'failed')
          )
          OR (
              new_status = 'cancelled'
              AND appointment.status IN ('pending', 'confirmed')
              AND appointment.sync_status IN ('pending', 'failed', 'synced')
          )
      )
    RETURNING appointment.* INTO updated_appointment;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Appointment not found or state transition denied'
            USING ERRCODE = '42501';
    END IF;

    RETURN NEXT updated_appointment;
END;
$$;

-- ============================================================
-- 6. Google refresh-token functions
-- ============================================================

CREATE OR REPLACE FUNCTION public.store_google_refresh_token(
    token_value text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    current_profile text := public.current_profile_id();
BEGIN
    IF current_profile IS NULL
       OR token_value IS NULL
       OR token_value = ''
    THEN
        RAISE EXCEPTION 'Authenticated profile and token required'
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO public.google_refresh_tokens (id, refresh_token, is_valid)
    VALUES (current_profile::uuid, token_value, true)
    ON CONFLICT (id) DO UPDATE
    SET refresh_token = EXCLUDED.refresh_token,
        is_valid = true;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_google_refresh_token(
    requested_profile_id text,
    backend_secret text
)
RETURNS TABLE (
    refresh_token text,
    is_valid boolean
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, private
AS $$
BEGIN
    PERFORM private.require_backend_secret(backend_secret);

    IF auth.uid() IS NOT NULL
       AND auth.uid()::text <> requested_profile_id
    THEN
        RAISE EXCEPTION 'Profile access denied'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT token.refresh_token, token.is_valid
    FROM public.google_refresh_tokens AS token
    WHERE token.id::text = requested_profile_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.invalidate_google_refresh_token(
    requested_profile_id text,
    backend_secret text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, private
AS $$
BEGIN
    PERFORM private.require_backend_secret(backend_secret);

    IF auth.uid() IS NOT NULL
       AND auth.uid()::text <> requested_profile_id
    THEN
        RAISE EXCEPTION 'Profile access denied'
            USING ERRCODE = '42501';
    END IF;

    UPDATE public.google_refresh_tokens
    SET is_valid = false
    WHERE id::text = requested_profile_id;
END;
$$;

-- ============================================================
-- 7. Backend reconciliation functions
-- ============================================================

CREATE OR REPLACE FUNCTION public.list_reconciliation_appointments(
    backend_secret text
)
RETURNS SETOF public.appointments
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, private
AS $$
BEGIN
    PERFORM private.require_backend_secret(backend_secret);

    RETURN QUERY
    SELECT appointment.*
    FROM public.appointments AS appointment
    WHERE appointment.status IN ('pending', 'confirmed');
END;
$$;

CREATE OR REPLACE FUNCTION public.update_reconciliation_appointment(
    backend_secret text,
    appointment_id uuid,
    new_status text,
    new_sync_status text,
    new_calendar_id text DEFAULT NULL,
    new_event_id text DEFAULT NULL,
    update_google_ids boolean DEFAULT false
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, private
AS $$
BEGIN
    PERFORM private.require_backend_secret(backend_secret);

    IF new_status NOT IN ('pending', 'confirmed', 'cancelled')
       OR new_sync_status NOT IN ('pending', 'synced', 'failed', 'legacy')
    THEN
        RAISE EXCEPTION 'Invalid reconciliation state'
            USING ERRCODE = '22023';
    END IF;

    UPDATE public.appointments
    SET status = new_status,
        sync_status = new_sync_status,
        google_calendar_id = CASE
            WHEN update_google_ids THEN new_calendar_id
            ELSE google_calendar_id
        END,
        google_event_id = CASE
            WHEN update_google_ids THEN new_event_id
            ELSE google_event_id
        END
    WHERE id = appointment_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Appointment not found'
            USING ERRCODE = 'P0002';
    END IF;
END;
$$;

-- ============================================================
-- 8. RLS and privileges
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
FROM PUBLIC, anon, authenticated;

-- Users can read their own profile and update onboarding fields.
GRANT SELECT ON TABLE public.users TO authenticated;
GRANT UPDATE (nim, major) ON TABLE public.users TO authenticated;

CREATE POLICY users_read_own_profile
ON public.users
FOR SELECT
TO authenticated
USING (id = auth.uid());

CREATE POLICY users_update_own_onboarding
ON public.users
FOR UPDATE
TO authenticated
USING (id = auth.uid())
WITH CHECK (id = auth.uid());

-- This preserves the current browser-mediated pending-booking design.
-- It must be removed if booking creation is moved exclusively to FastAPI.
GRANT SELECT ON TABLE public.appointments TO authenticated;

GRANT INSERT (
    id,
    booker_id,
    room_number,
    start_time,
    end_time,
    status,
    sync_status,
    replaces_appointment_id
)
ON TABLE public.appointments TO authenticated;

CREATE POLICY appointments_read_own
ON public.appointments
FOR SELECT
TO authenticated
USING (booker_id = auth.uid());

CREATE POLICY appointments_insert_own_pending
ON public.appointments
FOR INSERT
TO authenticated
WITH CHECK (
    booker_id = auth.uid()
    AND status = 'pending'
    AND sync_status = 'pending'
);

-- ============================================================
-- 9. Function execution permissions
-- ============================================================

REVOKE ALL ON FUNCTION public.current_profile_id()
    FROM PUBLIC, anon;

REVOKE ALL ON FUNCTION public.get_or_create_current_profile(text)
    FROM PUBLIC, anon;

REVOKE ALL ON FUNCTION public.get_booking_availability(date, integer, uuid)
    FROM PUBLIC, anon;

REVOKE ALL ON FUNCTION public.update_own_appointment_state(uuid, text, text)
    FROM PUBLIC, anon;

REVOKE ALL ON FUNCTION public.store_google_refresh_token(text)
    FROM PUBLIC, anon;

REVOKE ALL ON FUNCTION public.get_google_refresh_token(text, text)
    FROM PUBLIC;

REVOKE ALL ON FUNCTION public.invalidate_google_refresh_token(text, text)
    FROM PUBLIC;

REVOKE ALL ON FUNCTION public.list_reconciliation_appointments(text)
    FROM PUBLIC;

REVOKE ALL ON FUNCTION public.update_reconciliation_appointment(
    text, uuid, text, text, text, text, boolean
) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.current_profile_id()
    TO authenticated;

GRANT EXECUTE ON FUNCTION public.get_or_create_current_profile(text)
    TO authenticated;

GRANT EXECUTE ON FUNCTION public.get_booking_availability(date, integer, uuid)
    TO authenticated;

GRANT EXECUTE ON FUNCTION public.update_own_appointment_state(uuid, text, text)
    TO authenticated;

GRANT EXECUTE ON FUNCTION public.store_google_refresh_token(text)
    TO authenticated;

GRANT EXECUTE ON FUNCTION public.get_google_refresh_token(text, text)
    TO anon, authenticated;

GRANT EXECUTE ON FUNCTION public.invalidate_google_refresh_token(text, text)
    TO anon, authenticated;

GRANT EXECUTE ON FUNCTION public.list_reconciliation_appointments(text)
    TO anon, authenticated;

GRANT EXECUTE ON FUNCTION public.update_reconciliation_appointment(
    text, uuid, text, text, text, text, boolean
) TO anon, authenticated;

COMMIT;

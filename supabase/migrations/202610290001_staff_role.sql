BEGIN;

-- Staff role. Only an administrator sets it (SQL, never the app): students keep UPDATE on (nim, major) only,
-- so they cannot write this column. The jurusan "Dosen/Staff" is display only and carries no authority.
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'student';

ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_role_allowed;
ALTER TABLE public.users
    ADD CONSTRAINT users_role_allowed CHECK (role IN ('student', 'staff'));

-- Is the signed-in user staff? Used by policies and by the staff functions (migration 3).
CREATE OR REPLACE FUNCTION public.is_staff()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT coalesce(
        (SELECT u.role = 'staff' FROM public.users AS u WHERE u.id = auth.uid()),
        false
    );
$$;

REVOKE ALL ON FUNCTION public.is_staff() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_staff() TO authenticated;

-- The jurusan list gains "Dosen/Staff".
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_major_allowed;
ALTER TABLE public.users
    ADD CONSTRAINT users_major_allowed
    CHECK (
        major IS NULL
        OR major = ANY (ARRAY[
            'Information Technology',
            'Management',
            'Culinary Arts',
            'Visual Communication Design',
            'Accounting',
            'Architecture',
            'Business Information System',
            'Civil Engineering',
            'Hospitality & Tourism',
            'Interior Design',
            'Urban Planning',
            'Dosen/Staff'
        ]::text[])
    );

-- Staff may hold any number of bookings. Same function as 202610190001 plus the staff exemption.
CREATE OR REPLACE FUNCTION public.enforce_active_booking_limit()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
    active_count integer;
BEGIN
    -- Cancelled or already-finished rows never count (and must stay updatable by reconciliation).
    IF NEW.status NOT IN ('pending', 'confirmed') OR NEW.end_time <= now() THEN
        RETURN NEW;
    END IF;

    IF EXISTS (SELECT 1 FROM public.users WHERE id = NEW.booker_id AND role = 'staff') THEN
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

    PERFORM id
    FROM public.users
    WHERE id = NEW.booker_id
    FOR UPDATE;

    SELECT count(*)
    INTO active_count
    FROM public.appointments
    WHERE booker_id = NEW.booker_id
      AND status IN ('pending', 'confirmed')
      AND end_time > now()
      AND id <> NEW.id
      AND (
          NEW.replaces_appointment_id IS NULL
          OR id <> NEW.replaces_appointment_id
      );

    IF active_count >= 3 THEN
        RAISE EXCEPTION
            'A user may have at most three upcoming bookings'
            USING ERRCODE = 'P0001';
    END IF;

    RETURN NEW;
END;
$$;

-- The 5-minute lead and the 90-day window do not apply to staff (they may also record past slots).
CREATE OR REPLACE FUNCTION public.enforce_booking_window()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.users WHERE id = NEW.booker_id AND role = 'staff') THEN
        RETURN NEW;
    END IF;
    IF NEW.start_time < now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'Bookings close 5 minutes before the slot starts'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.start_time > now() + interval '90 days' THEN
        RAISE EXCEPTION 'Bookings open at most 90 days ahead'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;

-- Rollback (run by hand if needed): restore the two functions from 202610190001 and 202610230003, then
--   ALTER TABLE public.users DROP COLUMN role;  DROP FUNCTION public.is_staff();
-- and re-create users_major_allowed from 202610190005.
-- Promote someone (administrator, SQL editor):  UPDATE public.users SET role = 'staff' WHERE email = '<their email>';

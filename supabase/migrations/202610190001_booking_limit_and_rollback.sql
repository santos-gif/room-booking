BEGIN;

-- At most three upcoming active bookings per student, enforced at insert time.
-- Serialized per user by locking the user row, same as the daily limit it replaces.
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

DROP TRIGGER IF EXISTS appointments_daily_booking_limit
    ON public.appointments;
DROP TRIGGER IF EXISTS appointments_daily_user_booking_limit
    ON public.appointments;
DROP TRIGGER IF EXISTS appointments_active_booking_limit
    ON public.appointments;

CREATE TRIGGER appointments_active_booking_limit
BEFORE INSERT OR UPDATE OF
    booker_id,
    start_time,
    end_time,
    status,
    replaces_appointment_id
ON public.appointments
FOR EACH ROW
EXECUTE FUNCTION public.enforce_active_booking_limit();

DROP FUNCTION IF EXISTS public.enforce_daily_booking_limit();
DROP FUNCTION IF EXISTS public.enforce_daily_user_booking_limit();

-- Rollback for a booking whose Calendar event could not be created.
-- Only the owner's still-pending row can be removed, never a confirmed one.
CREATE OR REPLACE FUNCTION public.discard_own_pending_appointment(
    target_appointment_id uuid
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    current_profile text := public.current_profile_id();
BEGIN
    IF current_profile IS NULL THEN
        RAISE EXCEPTION 'Authenticated profile required'
            USING ERRCODE = '42501';
    END IF;

    DELETE FROM public.appointments
    WHERE id = target_appointment_id
      AND booker_id::text = current_profile
      AND status = 'pending';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pending appointment not found'
            USING ERRCODE = '42501';
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.discard_own_pending_appointment(uuid)
    FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.discard_own_pending_appointment(uuid)
    TO authenticated;

COMMIT;

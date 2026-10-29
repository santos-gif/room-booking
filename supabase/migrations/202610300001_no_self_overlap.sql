BEGIN;

-- One person cannot hold two rooms at the same time. The room-overlap constraint only compares bookings of the
-- SAME room, so the database never noticed a student booking 10:00-11:00 in both rooms. Staff are exempt (an event
-- may use both rooms). The booking this one replaces (a reschedule) is ignored, so moving rooms at the same hour works.
CREATE OR REPLACE FUNCTION public.enforce_no_self_overlap()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF NEW.status NOT IN ('pending', 'confirmed') THEN
        RETURN NEW;
    END IF;

    IF EXISTS (SELECT 1 FROM public.users WHERE id = NEW.booker_id AND role = 'staff') THEN
        RETURN NEW;
    END IF;

    -- Same per-user lock the booking limit takes, so two simultaneous requests cannot both pass.
    PERFORM id FROM public.users WHERE id = NEW.booker_id FOR UPDATE;

    IF EXISTS (
        SELECT 1
        FROM public.appointments AS other
        WHERE other.booker_id = NEW.booker_id
          AND other.id <> NEW.id
          AND other.status IN ('pending', 'confirmed')
          AND (NEW.replaces_appointment_id IS NULL OR other.id <> NEW.replaces_appointment_id)
          AND other.start_time < NEW.end_time
          AND other.end_time > NEW.start_time
    ) THEN
        RAISE EXCEPTION 'You already hold a room at that time'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS appointments_no_self_overlap ON public.appointments;
CREATE TRIGGER appointments_no_self_overlap
BEFORE INSERT OR UPDATE OF booker_id, room_number, start_time, end_time, status
ON public.appointments
FOR EACH ROW EXECUTE FUNCTION public.enforce_no_self_overlap();

COMMIT;

-- Rollback: DROP TRIGGER appointments_no_self_overlap ON public.appointments; DROP FUNCTION public.enforce_no_self_overlap();

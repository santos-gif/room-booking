BEGIN;

-- Server-side booking rules. The backend already checks them, but students hold the public API key and
-- can talk to Supabase directly, so the database must refuse what the backend refuses.

-- A new booking must start at least 5 minutes from now and within 90 days.
CREATE OR REPLACE FUNCTION public.enforce_booking_window()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
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

DROP TRIGGER IF EXISTS appointments_booking_window ON public.appointments;
CREATE TRIGGER appointments_booking_window
BEFORE INSERT ON public.appointments
FOR EACH ROW EXECUTE FUNCTION public.enforce_booking_window();

-- A booking may only become confirmed once its Google Calendar event is on record.
CREATE OR REPLACE FUNCTION public.enforce_confirmed_has_event()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF NEW.status = 'confirmed'
       AND OLD.status IS DISTINCT FROM 'confirmed'
       AND (NEW.google_event_id IS NULL OR NEW.google_calendar_id IS NULL)
    THEN
        RAISE EXCEPTION 'A confirmed booking needs its calendar event'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS appointments_confirmed_has_event ON public.appointments;
CREATE TRIGGER appointments_confirmed_has_event
BEFORE UPDATE OF status ON public.appointments
FOR EACH ROW EXECUTE FUNCTION public.enforce_confirmed_has_event();

-- The display name ends up in the shared room calendar: one clean line, at most 80 characters.
-- Cleaned, never rejected, so a sign-in can not fail because of an odd name from Google.
CREATE OR REPLACE FUNCTION public.clean_user_name()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    NEW.name := left(
        btrim(regexp_replace(regexp_replace(NEW.name, '[[:cntrl:]]', ' ', 'g'), '\s+', ' ', 'g')),
        80
    );
    IF NEW.name = '' THEN
        NEW.name := split_part(NEW.email, '@', 1);
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS users_clean_name ON public.users;
CREATE TRIGGER users_clean_name
BEFORE INSERT OR UPDATE OF name ON public.users
FOR EACH ROW EXECUTE FUNCTION public.clean_user_name();

-- One NIM, one student. (Students can still edit their own NIM; making it write-once is a product decision.)
CREATE UNIQUE INDEX IF NOT EXISTS users_nim_uidx
    ON public.users (nim)
    WHERE nim IS NOT NULL;

COMMIT;

BEGIN;

-- A room can be closed for a range of dates (past dates allowed: staff may record what already happened).
CREATE TABLE IF NOT EXISTS public.room_closures (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_number integer NOT NULL CHECK (room_number IN (1, 2)),
    start_date date NOT NULL,
    end_date date NOT NULL,
    reason text NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 1 AND 200),
    created_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT room_closures_dates_ordered CHECK (end_date >= start_date),
    CONSTRAINT room_closures_max_length CHECK (end_date - start_date <= 366)
);

CREATE INDEX IF NOT EXISTS room_closures_room_dates_idx
    ON public.room_closures (room_number, start_date, end_date);

-- A message for a student whose booking staff cancelled. Shown in My bookings until dismissed.
CREATE TABLE IF NOT EXISTS public.booking_notices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    message text NOT NULL CHECK (char_length(message) <= 500),
    created_at timestamptz NOT NULL DEFAULT now(),
    seen_at timestamptz
);

CREATE INDEX IF NOT EXISTS booking_notices_user_idx
    ON public.booking_notices (user_id, created_at DESC);

-- Who did what, for the administrators. Written only by the staff functions.
CREATE TABLE IF NOT EXISTS public.staff_audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id uuid REFERENCES public.users(id) ON DELETE SET NULL,
    action text NOT NULL,
    room_number integer,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.room_closures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.booking_notices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.staff_audit_log ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.room_closures, public.booking_notices, public.staff_audit_log
    FROM PUBLIC, anon, authenticated;

GRANT SELECT ON TABLE public.room_closures TO authenticated;
GRANT SELECT ON TABLE public.booking_notices TO authenticated;
GRANT UPDATE (seen_at) ON TABLE public.booking_notices TO authenticated;
GRANT SELECT ON TABLE public.staff_audit_log TO authenticated;

DROP POLICY IF EXISTS room_closures_read ON public.room_closures;
CREATE POLICY room_closures_read ON public.room_closures
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS booking_notices_read_own ON public.booking_notices;
CREATE POLICY booking_notices_read_own ON public.booking_notices
    FOR SELECT TO authenticated USING (user_id = auth.uid());

DROP POLICY IF EXISTS booking_notices_dismiss_own ON public.booking_notices;
CREATE POLICY booking_notices_dismiss_own ON public.booking_notices
    FOR UPDATE TO authenticated
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS staff_audit_log_read_staff ON public.staff_audit_log;
CREATE POLICY staff_audit_log_read_staff ON public.staff_audit_log
    FOR SELECT TO authenticated USING (public.is_staff());

-- No new active booking inside a closed range. Insert only: reconciliation updates must stay possible.
-- Students can talk to Supabase directly with the public key, so the database refuses it too.
CREATE OR REPLACE FUNCTION public.enforce_room_closure()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF NEW.status IN ('pending', 'confirmed')
       AND EXISTS (
            SELECT 1
            FROM public.room_closures AS closure
            WHERE closure.room_number = NEW.room_number
              AND (NEW.start_time AT TIME ZONE 'Asia/Jakarta')::date
                  BETWEEN closure.start_date AND closure.end_date
       )
    THEN
        RAISE EXCEPTION 'The room is closed on that date'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS appointments_room_closure ON public.appointments;
CREATE TRIGGER appointments_room_closure
BEFORE INSERT ON public.appointments
FOR EACH ROW EXECUTE FUNCTION public.enforce_room_closure();

COMMIT;

-- Rollback: DROP TRIGGER appointments_room_closure ON public.appointments; DROP FUNCTION public.enforce_room_closure();
--   DROP TABLE public.staff_audit_log, public.booking_notices, public.room_closures;

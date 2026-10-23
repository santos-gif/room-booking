BEGIN;

-- Rows nobody can see or book any more: cancelled ones, and confirmed ones whose end time has passed.
-- end_time is timestamptz, so "passed" is an exact instant comparison: Jakarta time (UTC+7) and UTC agree.
-- Pending rows are left to the reconciliation job. A row that a later row still replaces is kept
-- (foreign key), and removed on a later pass once that later row is gone too.
CREATE OR REPLACE FUNCTION public.purge_finished_appointments(backend_secret text)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, private
AS $$
DECLARE
    removed integer;
    total integer := 0;
BEGIN
    PERFORM private.require_backend_secret(backend_secret);

    -- A chain of replacements frees one link per pass, so repeat (bounded).
    FOR pass IN 1..10 LOOP
        DELETE FROM public.appointments AS appointment
        WHERE (
            appointment.status = 'cancelled'
            OR (appointment.status = 'confirmed' AND appointment.end_time < now())
        )
        AND NOT EXISTS (
            SELECT 1
            FROM public.appointments AS later
            WHERE later.replaces_appointment_id = appointment.id
        );
        GET DIAGNOSTICS removed = ROW_COUNT;
        total := total + removed;
        EXIT WHEN removed = 0;
    END LOOP;

    RETURN total;
END;
$$;

-- Lets a student's own cancelled booking be removed right away (the owner cancelled it, or its
-- Google event was deleted). Only the caller's own cancelled, unreferenced row can go.
CREATE OR REPLACE FUNCTION public.remove_own_cancelled_appointment(target_appointment_id uuid)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    current_profile text := public.current_profile_id();
    removed integer;
BEGIN
    IF current_profile IS NULL THEN
        RAISE EXCEPTION 'Authenticated profile required'
            USING ERRCODE = '42501';
    END IF;

    DELETE FROM public.appointments AS appointment
    WHERE appointment.id = target_appointment_id
      AND appointment.booker_id::text = current_profile
      AND appointment.status = 'cancelled'
      AND NOT EXISTS (
          SELECT 1
          FROM public.appointments AS later
          WHERE later.replaces_appointment_id = appointment.id
      );

    GET DIAGNOSTICS removed = ROW_COUNT;
    RETURN removed = 1;
END;
$$;

REVOKE ALL ON FUNCTION public.purge_finished_appointments(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.remove_own_cancelled_appointment(uuid) FROM PUBLIC;

-- Same pattern as the other backend-secret functions: the secret check inside is the lock.
GRANT EXECUTE ON FUNCTION public.purge_finished_appointments(text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.remove_own_cancelled_appointment(uuid) TO authenticated;

COMMIT;

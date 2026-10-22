BEGIN;

-- Lets reconciliation tell a dead pending booking from one whose request is still running.
-- Clients cannot set it: INSERT is column-limited and this column is not in the grant.
ALTER TABLE public.appointments
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

-- Removes a pending booking only if it is still pending and older than the grace period,
-- so a late cleanup can never delete a booking that has since been confirmed.
CREATE OR REPLACE FUNCTION public.discard_stale_pending_appointment(
    backend_secret text,
    appointment_id uuid,
    min_age_seconds integer
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, private
AS $$
DECLARE
    removed integer;
BEGIN
    PERFORM private.require_backend_secret(backend_secret);

    DELETE FROM public.appointments
    WHERE id = appointment_id
      AND status = 'pending'
      AND created_at < now() - make_interval(secs => min_age_seconds);

    GET DIAGNOSTICS removed = ROW_COUNT;
    RETURN removed = 1;
END;
$$;

REVOKE ALL ON FUNCTION public.discard_stale_pending_appointment(text, uuid, integer)
    FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.discard_stale_pending_appointment(text, uuid, integer)
    TO anon, authenticated;

COMMIT;

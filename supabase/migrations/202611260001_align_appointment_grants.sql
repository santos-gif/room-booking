BEGIN;

-- Make the repo and production agree on what a signed-in student's token may do to appointments (issue #20).

-- Needed: the backend inserts a booking with the student's own token, including the Calendar ids it chose
-- (app/api/v1/appointment/booking.py). Production already has this; a fresh install did not, so booking failed.
GRANT INSERT (google_calendar_id, google_event_id) ON public.appointments TO authenticated;

-- Not needed: nothing updates appointments with the student's token. Every status change goes through
-- SECURITY DEFINER functions, so the direct UPDATE right that only production still had is removed.
-- Revoking on the table also revokes the column-level UPDATE(status).
DROP POLICY IF EXISTS appointments_update_own ON public.appointments;
REVOKE UPDATE ON public.appointments FROM authenticated;

COMMIT;

-- Rollback: GRANT UPDATE (status) ON public.appointments TO authenticated; and recreate the policy:
-- CREATE POLICY appointments_update_own ON public.appointments FOR UPDATE TO authenticated
--   USING (booker_id = auth.uid())
--   WITH CHECK (booker_id = auth.uid() AND status IN ('pending', 'confirmed', 'cancelled'));

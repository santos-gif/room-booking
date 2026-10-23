BEGIN;

-- Both are for signed-in students only. They already refuse callers without a profile (42501),
-- but anon should not be able to reach them at all (a later change had re-granted PUBLIC).
REVOKE ALL ON FUNCTION public.update_own_appointment_state(uuid, text, text) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.remove_own_cancelled_appointment(uuid) FROM PUBLIC, anon;

GRANT EXECUTE ON FUNCTION public.update_own_appointment_state(uuid, text, text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.remove_own_cancelled_appointment(uuid) TO authenticated;

-- Trigger functions run from their triggers; nobody needs to call them over the API.
-- Guarded: either may be missing on a fresh database (one is created outside the migrations).
DO $$
BEGIN
    IF to_regprocedure('public.handle_new_auth_user()') IS NOT NULL THEN
        REVOKE ALL ON FUNCTION public.handle_new_auth_user() FROM PUBLIC, anon, authenticated;
    END IF;
    IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN
        REVOKE ALL ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;
    END IF;
END
$$;

COMMIT;

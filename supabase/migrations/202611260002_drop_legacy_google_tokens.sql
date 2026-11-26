BEGIN;

-- Remove the per-student Google token storage (issue #2). One service account writes the calendars now and
-- sign-in asks for identity only, so nothing reads or writes these objects. Approved proposal:
-- hitl/explorations/remove-legacy-google-tokens-proposal.md

-- Guard: stop if the table holds more than the one known leftover row.
DO $$
BEGIN
    IF to_regclass('public.google_refresh_tokens') IS NOT NULL THEN
        IF (SELECT count(*) FROM public.google_refresh_tokens) > 1 THEN
            RAISE EXCEPTION 'Expected at most 1 legacy token row: check who wrote the others before dropping';
        END IF;
    END IF;
END;
$$;

DROP FUNCTION IF EXISTS public.get_google_refresh_token(text, text);
DROP FUNCTION IF EXISTS public.invalidate_google_refresh_token(text, text);
DROP FUNCTION IF EXISTS public.store_google_refresh_token(text);
DROP TABLE IF EXISTS public.google_refresh_tokens;

COMMIT;

-- Rollback: re-run the table definition from supabase/main.sql (section 0) and the three function definitions
-- from 202610100001_supabase_auth_identity.sql. The old token itself cannot be restored and is not needed.

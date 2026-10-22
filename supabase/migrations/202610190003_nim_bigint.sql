BEGIN;

-- Real NIMs have 10 digits (e.g. 2510101051), above the 2,147,483,647 an integer can hold,
-- so onboarding failed with "value is out of range for type integer". Widening keeps the
-- unique key and the nim > 0 check; no SQL function or view references this column.
ALTER TABLE public.users
    ALTER COLUMN nim TYPE bigint;

COMMIT;

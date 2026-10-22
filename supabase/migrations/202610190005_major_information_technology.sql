BEGIN;

-- The app now stores the full name 'Information Technology' instead of 'IT'.
-- Drop the check, convert existing rows, then re-add the check with the new list.
ALTER TABLE public.users
    DROP CONSTRAINT IF EXISTS users_major_allowed;

UPDATE public.users
SET major = 'Information Technology'
WHERE major = 'IT';

ALTER TABLE public.users
    ADD CONSTRAINT users_major_allowed
    CHECK (
        major IS NULL
        OR major = ANY (ARRAY[
            'Information Technology',
            'Management',
            'Culinary Arts',
            'Visual Communication Design',
            'Accounting',
            'Architecture',
            'Business Information System',
            'Civil Engineering',
            'Hospitality & Tourism',
            'Interior Design',
            'Urban Planning'
        ]::text[])
    );

COMMIT;

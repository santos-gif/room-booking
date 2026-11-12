BEGIN;

-- Two closures of the same room must not share a day. The staff screen and the backend already refuse
-- it; this makes the database the last word, also against two staff members closing at the same moment.
-- btree_gist is already installed (the bookings use it for their own overlap rule).

-- Existing overlaps would make the constraint fail halfway: stop first, with a message that says what to do.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.room_closures AS a
        JOIN public.room_closures AS b
          ON a.room_number = b.room_number
         AND a.id < b.id
         AND daterange(a.start_date, a.end_date, '[]') && daterange(b.start_date, b.end_date, '[]')
    ) THEN
        RAISE EXCEPTION 'Overlapping closures exist: use Reopen on the Staff page for one of each pair, then run this again';
    END IF;
END;
$$;

ALTER TABLE public.room_closures
    DROP CONSTRAINT IF EXISTS room_closures_no_overlap;
ALTER TABLE public.room_closures
    ADD CONSTRAINT room_closures_no_overlap
    EXCLUDE USING gist (
        room_number WITH =,
        daterange(start_date, end_date, '[]') WITH &&
    );

COMMIT;

-- Rollback: ALTER TABLE public.room_closures DROP CONSTRAINT room_closures_no_overlap;

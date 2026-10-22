BEGIN;

-- bookings_used now counts the student's upcoming active bookings across all days, matching
-- the trigger enforce_active_booking_limit (max 3). Before, it counted only the chosen day,
-- so the page showed the wrong "bookings remaining". Same signature and return type.
CREATE OR REPLACE FUNCTION public.get_booking_availability(
    booking_date date,
    requested_room integer,
    excluded_appointment_id uuid DEFAULT NULL
)
RETURNS TABLE (
    booked_starts timestamptz[],
    bookings_used bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    current_profile text := public.current_profile_id();
    day_start timestamptz;
BEGIN
    IF current_profile IS NULL THEN
        RAISE EXCEPTION 'Invalid availability request'
            USING ERRCODE = '42501';
    END IF;

    IF booking_date IS NULL
       OR requested_room IS NULL
       OR requested_room NOT IN (1, 2)
    THEN
        RAISE EXCEPTION 'Invalid availability request'
            USING ERRCODE = '22023';
    END IF;

    IF excluded_appointment_id IS NOT NULL
       AND NOT EXISTS (
            SELECT 1
            FROM public.appointments AS owned
            WHERE owned.id = excluded_appointment_id
              AND owned.booker_id::text = current_profile
              AND owned.status IN ('pending', 'confirmed')
       )
    THEN
        RAISE EXCEPTION 'Appointment access denied'
            USING ERRCODE = '42501';
    END IF;

    day_start := booking_date::timestamp AT TIME ZONE 'Asia/Jakarta';

    RETURN QUERY
    SELECT
        coalesce(
            (
                SELECT array_agg(a.start_time)
                FROM public.appointments AS a
                WHERE a.status IN ('pending', 'confirmed')
                  AND a.room_number = requested_room
                  AND a.start_time >= day_start
                  AND a.start_time < day_start + interval '1 day'
                  AND (
                      excluded_appointment_id IS NULL
                      OR a.id <> excluded_appointment_id
                  )
            ),
            '{}'::timestamptz[]
        ),
        (
            SELECT count(*)
            FROM public.appointments AS a
            WHERE a.status IN ('pending', 'confirmed')
              AND a.booker_id::text = current_profile
              AND a.end_time > now()
              AND (
                  excluded_appointment_id IS NULL
                  OR a.id <> excluded_appointment_id
              )
        );
END;
$$;

COMMIT;

BEGIN;

-- Cancels the given active bookings for staff: status cancelled, sync pending (the Google event is deleted
-- afterwards and then marked synced; the nightly job retries what failed) and one notice per student.
CREATE OR REPLACE FUNCTION private.staff_cancel_rows(p_ids uuid[], p_reason text, p_actor uuid)
RETURNS SETOF public.appointments
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    RETURN QUERY
    WITH cancelled AS (
        UPDATE public.appointments AS a
        SET status = 'cancelled', sync_status = 'pending'
        WHERE a.id = ANY (p_ids) AND a.status IN ('pending', 'confirmed')
        RETURNING a.*
    ), notices AS (
        INSERT INTO public.booking_notices (user_id, message)
        SELECT c.booker_id,
               left(format(
                   'Your booking of Discussion Room %s on %s at %s WIB was cancelled by staff: %s',
                   c.room_number,
                   to_char(c.start_time AT TIME ZONE 'Asia/Jakarta', 'DD Mon YYYY'),
                   to_char(c.start_time AT TIME ZONE 'Asia/Jakarta', 'HH24:MI'),
                   p_reason
               ), 500)
        FROM cancelled AS c
        WHERE c.booker_id IS DISTINCT FROM p_actor
        RETURNING 1
    )
    SELECT * FROM cancelled;
END;
$$;

REVOKE ALL ON FUNCTION private.staff_cancel_rows(uuid[], text, uuid) FROM PUBLIC, anon, authenticated;

-- Who holds a room in a time range (the closure preview and the override screen). Staff only.
CREATE OR REPLACE FUNCTION public.staff_list_bookings(
    p_room integer, p_from timestamptz, p_to timestamptz, p_future_only boolean DEFAULT true
)
RETURNS TABLE (
    appointment_id uuid, booker_id uuid, booker_name text, booker_nim bigint, booker_email text,
    room_number integer, start_time timestamptz, end_time timestamptz, status text
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF NOT public.is_staff() THEN
        RAISE EXCEPTION 'Staff only' USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT a.id, a.booker_id, u.name::text, u.nim::bigint, u.email::text,
           a.room_number::integer, a.start_time, a.end_time, a.status::text
    FROM public.appointments AS a
    JOIN public.users AS u ON u.id = a.booker_id
    WHERE a.room_number = p_room
      AND a.status IN ('pending', 'confirmed')
      AND a.start_time < p_to
      AND a.end_time > p_from
      AND (NOT p_future_only OR a.end_time > now())
    ORDER BY a.start_time;
END;
$$;

-- Close a room for a date range (past dates allowed): record it, cancel every active booking inside it.
CREATE OR REPLACE FUNCTION public.staff_create_closure(
    p_room integer, p_start date, p_end date, p_reason text
)
RETURNS SETOF public.appointments
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    actor uuid := auth.uid();
    ids uuid[];
BEGIN
    IF NOT public.is_staff() THEN
        RAISE EXCEPTION 'Staff only' USING ERRCODE = '42501';
    END IF;
    IF p_room NOT IN (1, 2) OR p_start IS NULL OR p_end IS NULL OR p_end < p_start
       OR p_end - p_start > 366 OR p_reason IS NULL
       OR char_length(btrim(p_reason)) NOT BETWEEN 1 AND 200
    THEN
        RAISE EXCEPTION 'Invalid closure' USING ERRCODE = '22023';
    END IF;

    -- Blocks concurrent bookings for the moment, so none slips in between the list and the closure.
    LOCK TABLE public.appointments IN SHARE ROW EXCLUSIVE MODE;

    INSERT INTO public.room_closures (room_number, start_date, end_date, reason, created_by)
    VALUES (p_room, p_start, p_end, btrim(p_reason), actor);

    SELECT coalesce(array_agg(a.id), '{}'::uuid[]) INTO ids
    FROM public.appointments AS a
    WHERE a.room_number = p_room
      AND a.status IN ('pending', 'confirmed')
      AND a.end_time > now()
      AND (a.start_time AT TIME ZONE 'Asia/Jakarta')::date BETWEEN p_start AND p_end;

    INSERT INTO public.staff_audit_log (actor_id, action, room_number, details)
    VALUES (actor, 'closure_created', p_room, jsonb_build_object(
        'start', p_start, 'end', p_end, 'reason', btrim(p_reason), 'cancelled', cardinality(ids)));

    RETURN QUERY SELECT * FROM private.staff_cancel_rows(ids, btrim(p_reason), actor);
END;
$$;

CREATE OR REPLACE FUNCTION public.staff_delete_closure(p_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    removed public.room_closures;
BEGIN
    IF NOT public.is_staff() THEN
        RAISE EXCEPTION 'Staff only' USING ERRCODE = '42501';
    END IF;
    DELETE FROM public.room_closures WHERE id = p_id RETURNING * INTO removed;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Closure not found' USING ERRCODE = 'P0002';
    END IF;
    INSERT INTO public.staff_audit_log (actor_id, action, room_number, details)
    VALUES (auth.uid(), 'closure_deleted', removed.room_number, jsonb_build_object(
        'start', removed.start_date, 'end', removed.end_date, 'reason', removed.reason));
END;
$$;

-- Take one slot for staff: cancel whoever holds it (they get a notice) and insert the staff booking as
-- pending, with the id and Google ids the backend chose (its event already exists). The backend then confirms it.
CREATE OR REPLACE FUNCTION public.staff_override_slot(
    p_room integer, p_start timestamptz, p_reason text, p_calendar_id text, p_event_id text, p_hold_id uuid
)
RETURNS SETOF public.appointments
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    actor uuid := auth.uid();
    ids uuid[];
BEGIN
    IF NOT public.is_staff() THEN
        RAISE EXCEPTION 'Staff only' USING ERRCODE = '42501';
    END IF;
    IF p_room NOT IN (1, 2) OR p_start IS NULL OR p_reason IS NULL
       OR char_length(btrim(p_reason)) NOT BETWEEN 1 AND 200
       OR coalesce(p_calendar_id, '') = '' OR coalesce(p_event_id, '') = '' OR p_hold_id IS NULL
    THEN
        RAISE EXCEPTION 'Invalid override' USING ERRCODE = '22023';
    END IF;

    LOCK TABLE public.appointments IN SHARE ROW EXCLUSIVE MODE;

    SELECT coalesce(array_agg(a.id), '{}'::uuid[]) INTO ids
    FROM public.appointments AS a
    WHERE a.room_number = p_room
      AND a.status IN ('pending', 'confirmed')
      AND a.start_time < p_start + interval '1 hour'
      AND a.end_time > p_start;

    RETURN QUERY SELECT * FROM private.staff_cancel_rows(ids, btrim(p_reason), actor);

    INSERT INTO public.appointments (
        id, booker_id, room_number, start_time, end_time, status, sync_status,
        google_calendar_id, google_event_id
    ) VALUES (
        p_hold_id, actor, p_room, p_start, p_start + interval '1 hour', 'pending', 'pending',
        p_calendar_id, p_event_id
    );

    INSERT INTO public.staff_audit_log (actor_id, action, room_number, details)
    VALUES (actor, 'slot_override', p_room, jsonb_build_object(
        'start', p_start, 'reason', btrim(p_reason), 'cancelled', cardinality(ids)));

    RETURN QUERY SELECT * FROM public.appointments WHERE id = p_hold_id;
END;
$$;

-- The backend deleted these cancelled bookings' Google events: the nightly job need not retry them.
CREATE OR REPLACE FUNCTION public.staff_mark_synced(p_ids uuid[])
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    done integer;
BEGIN
    IF NOT public.is_staff() THEN
        RAISE EXCEPTION 'Staff only' USING ERRCODE = '42501';
    END IF;
    UPDATE public.appointments
    SET sync_status = 'synced'
    WHERE id = ANY (p_ids) AND status = 'cancelled' AND sync_status = 'pending';
    GET DIAGNOSTICS done = ROW_COUNT;
    RETURN done;
END;
$$;

REVOKE ALL ON FUNCTION
    public.staff_list_bookings(integer, timestamptz, timestamptz, boolean),
    public.staff_create_closure(integer, date, date, text),
    public.staff_delete_closure(uuid),
    public.staff_override_slot(integer, timestamptz, text, text, text, uuid),
    public.staff_mark_synced(uuid[])
FROM PUBLIC, anon;

GRANT EXECUTE ON FUNCTION
    public.staff_list_bookings(integer, timestamptz, timestamptz, boolean),
    public.staff_create_closure(integer, date, date, text),
    public.staff_delete_closure(uuid),
    public.staff_override_slot(integer, timestamptz, text, text, text, uuid),
    public.staff_mark_synced(uuid[])
TO authenticated;

-- The nightly job also sees cancelled bookings whose Google event is not confirmed deleted yet.
CREATE OR REPLACE FUNCTION public.list_reconciliation_appointments(backend_secret text)
RETURNS SETOF public.appointments
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, private
AS $$
BEGIN
    PERFORM private.require_backend_secret(backend_secret);

    RETURN QUERY
    SELECT appointment.*
    FROM public.appointments AS appointment
    WHERE appointment.status IN ('pending', 'confirmed')
       OR (appointment.status = 'cancelled' AND appointment.sync_status = 'pending');
END;
$$;

-- Garbage collection must not drop a cancelled booking before its Google event is gone.
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

    FOR pass IN 1..10 LOOP
        DELETE FROM public.appointments AS appointment
        WHERE (
            (appointment.status = 'cancelled' AND appointment.sync_status <> 'pending')
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

COMMIT;

-- Rollback: DROP the five public.staff_* functions and private.staff_cancel_rows; restore
-- list_reconciliation_appointments (202610100001) and purge_finished_appointments (202610230001).

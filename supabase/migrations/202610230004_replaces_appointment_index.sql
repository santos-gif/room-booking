BEGIN;

-- The purge and the foreign key both ask "does any row (of any status) replace this one?". The only
-- existing index on this column covers active rows only, so those lookups scanned the table.
-- Almost every row has NULL here, so this partial index stays tiny.
CREATE INDEX IF NOT EXISTS appointments_replaces_idx
    ON public.appointments (replaces_appointment_id)
    WHERE replaces_appointment_id IS NOT NULL;

COMMIT;

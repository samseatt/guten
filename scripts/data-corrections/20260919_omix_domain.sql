-- Requested domain spelling correction; cloud Guten only, not a publish operation.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
DO $$
BEGIN
  IF current_database() <> 'guten_datalake' THEN
    RAISE EXCEPTION 'Expected Guten production database';
  END IF;
  IF (SELECT count(*) FROM draft.sites WHERE id=48 AND name='omix' AND url='omics.cc') <> 1
     OR (SELECT count(*) FROM published.sites WHERE id=48 AND name='omix' AND url='omics.cc') <> 1 THEN
    RAISE EXCEPTION 'Unexpected Omix state; inspect rather than overwrite';
  END IF;
  UPDATE draft.sites SET url='omix.cc', updated_at=CURRENT_TIMESTAMP WHERE id=48 AND name='omix';
  UPDATE published.sites SET url='omix.cc', updated_at=CURRENT_TIMESTAMP WHERE id=48 AND name='omix';
END $$;
SELECT 'draft' AS schema,id,name,url FROM draft.sites WHERE id=48
UNION ALL SELECT 'published',id,name,url FROM published.sites WHERE id=48;
COMMIT;

-- Delete in FK order: children first, then parents
-- activity -> area (FK), activity -> platform (FK)
-- Also delete rows linked to sdep-test-* parents (e.g. auto-generated UUIDs)

-- Delete activities in batches (10 000 rows per transaction) to avoid
-- long-running transactions that can time out under load.
-- Matches by activity_id prefix OR by area reference, so activities with
-- auto-generated UUIDs submitted to sdep-test-* areas are also cleaned up.
CREATE OR REPLACE PROCEDURE _clean_testrun_activities(batch_size INT DEFAULT 10000)
LANGUAGE plpgsql AS $$
DECLARE
  deleted INT;
BEGIN
  LOOP
    DELETE FROM activity
    WHERE id IN (
      SELECT a.id FROM activity a
      WHERE a.activity_id LIKE 'sdep-test-%'
         OR a.area_id IN (SELECT id FROM area WHERE area_id LIKE 'sdep-test-%')
      LIMIT batch_size
    );
    GET DIAGNOSTICS deleted = ROW_COUNT;
    RAISE NOTICE 'Deleted % activities', deleted;
    EXIT WHEN deleted = 0;
    COMMIT;
  END LOOP;
END $$;

CALL _clean_testrun_activities();
DROP PROCEDURE _clean_testrun_activities;

DELETE FROM area WHERE area_id LIKE 'sdep-test-%'
    OR competent_authority_id IN (
        SELECT id FROM competent_authority
        WHERE client_id LIKE 'sdep-test-%'
    );
DELETE FROM platform WHERE client_id LIKE 'sdep-test-%';
DELETE FROM competent_authority WHERE client_id LIKE 'sdep-test-%';

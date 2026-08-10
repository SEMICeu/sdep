-- Delete in FK order: children first, then parents
-- activity -> area (FK), activity -> platform (FK)
-- Also delete rows linked to sdep-test-* parents (e.g. auto-generated UUIDs)

-- Delete activities in batches (10 000 rows per transaction) to avoid
-- long-running transactions that can time out under load.
-- Matches by activity_id prefix OR by area reference, so activities with
-- auto-generated UUIDs submitted to sdep-test-* areas are also cleaned up.
-- activity has two parents, so this predicate must cover every row that either
-- parent delete below would orphan; otherwise that delete fails on its foreign key:
--   - fk_activity_area_id_area      -> the area sub-select must match DELETE FROM area
--   - fk_activity_platform_id_platform -> the platform sub-select must match
--                                         DELETE FROM platform
-- Matching by activity_id alone is not enough. An area with an auto-generated UUID
-- area_id owned by an sdep-test-* competent authority (created when POSTing an area
-- without areaId) and an activity submitted by an sdep-test-* platform under a
-- non-test id both slip through it.
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
         OR a.area_id IN (
              SELECT id FROM area
              WHERE area_id LIKE 'sdep-test-%'
                 OR competent_authority_id IN (
                      SELECT id FROM competent_authority
                      WHERE client_id LIKE 'sdep-test-%'
                    )
            )
         OR a.platform_id IN (
              SELECT id FROM platform WHERE client_id LIKE 'sdep-test-%'
            )
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

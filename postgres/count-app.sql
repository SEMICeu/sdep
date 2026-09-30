-- Row count per table, for the test isolation check (see scripts/run-tests.sh).
-- Excludes audit_log: tests add audit rows, cleanup keeps them.
-- So its count always grows, and the check would always fail.
SELECT 'competent_authority' AS table_name, COUNT(*) AS row_count FROM competent_authority
UNION ALL
SELECT 'area', COUNT(*) FROM area
UNION ALL
SELECT 'platform', COUNT(*) FROM platform
UNION ALL
SELECT 'activity', COUNT(*) FROM activity
UNION ALL
SELECT 'listing', COUNT(*) FROM listing
ORDER BY table_name;

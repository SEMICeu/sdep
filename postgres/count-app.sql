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
UNION ALL
SELECT 'competent_authority_identity', COUNT(*) FROM competent_authority_identity
UNION ALL
SELECT 'platform_identity', COUNT(*) FROM platform_identity
UNION ALL
SELECT 'area_identity', COUNT(*) FROM area_identity
UNION ALL
SELECT 'activity_identity', COUNT(*) FROM activity_identity
UNION ALL
SELECT 'listing_identity', COUNT(*) FROM listing_identity
ORDER BY table_name;

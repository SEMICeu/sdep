SELECT 'competent_authority' AS table_name, COUNT(*) AS row_count FROM competent_authority
UNION ALL
SELECT 'area', COUNT(*) FROM area
UNION ALL
SELECT 'platform', COUNT(*) FROM platform
UNION ALL
SELECT 'activity', COUNT(*) FROM activity
ORDER BY table_name;

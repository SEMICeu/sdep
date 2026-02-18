-- Drop and recreate application database

-- Revoke connect privileges to prevent new connections
REVOKE CONNECT ON DATABASE "sdep-data" FROM public;

-- Terminate all active connections to the database
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = 'sdep-data'
  AND pid <> pg_backend_pid();

-- Drop the database
DROP DATABASE "sdep-data";

-- Recreate the database
CREATE DATABASE "sdep-data";

-- Grant privileges to the application user
GRANT ALL PRIVILEGES ON DATABASE "sdep-data" TO sdep;

-- Connect to the new database and grant schema privileges
\c sdep-data
GRANT ALL ON SCHEMA public TO sdep;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sdep;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sdep;

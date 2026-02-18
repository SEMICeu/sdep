-- Create sdep-data database and user (idempotent)
SELECT 'CREATE DATABASE "sdep-data"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sdep-data')\gexec

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sdep') THEN
    CREATE USER sdep WITH ENCRYPTED PASSWORD 'sdep';
  END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE "sdep-data" TO sdep;

-- Switch to sdep-data database and grant schema privileges
\c "sdep-data"
GRANT ALL ON SCHEMA public TO sdep;

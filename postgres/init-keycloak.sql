-- Create keycloak database and user (idempotent)
SELECT 'CREATE DATABASE keycloak'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'keycloak') THEN
    CREATE USER keycloak WITH ENCRYPTED PASSWORD 'keycloak';
  END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;

-- Switch to keycloak database and grant schema privileges
\c keycloak
GRANT ALL ON SCHEMA public TO keycloak;

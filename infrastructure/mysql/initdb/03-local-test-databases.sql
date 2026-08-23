-- Local/test database provisioning (LOCAL ONLY — never production).
--
-- Idempotent and NON-destructive: safe to re-run against an existing
-- Docker volume. Creates the two dedicated test schemas required by the
-- Phase 3A review and scopes appuser privileges to them only.
--
--   taskdb                  : normal local development (pytest must NOT
--                             destructively modify it)
--   taskdb_test             : ordinary pytest integration/API/session tests
--                             (cleanup/truncation allowed HERE only)
--   taskdb_migration_test   : destructive Alembic round-trip tests only

CREATE DATABASE IF NOT EXISTS `taskdb_test` CHARACTER SET utf8mb4;
CREATE DATABASE IF NOT EXISTS `taskdb_migration_test` CHARACTER SET utf8mb4;

GRANT ALL PRIVILEGES ON `taskdb_test`.* TO 'appuser'@'%';
GRANT ALL PRIVILEGES ON `taskdb_migration_test`.* TO 'appuser'@'%';
FLUSH PRIVILEGES;

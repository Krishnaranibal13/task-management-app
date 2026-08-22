-- Scoped privilege for migration-integrity tests (LOCAL DEV ONLY).
--
-- Destructive Alembic round-trip tests run exclusively against the
-- disposable database `taskdb_migration_test`. This grant gives the
-- application's LOCAL dev user rights on that single throwaway schema
-- only — it does not affect the development database `taskdb` beyond
-- its existing usage grants, and it is not a production credential or
-- privilege change.
GRANT ALL PRIVILEGES ON `taskdb_migration_test`.* TO 'appuser'@'%';
FLUSH PRIVILEGES;

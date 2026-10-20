-- PromoSearch: acesso de execucao restrito ao schema radar.
-- Execute somente depois de criar radar_app. Nao define nem mostra senhas.
BEGIN;
GRANT USAGE ON SCHEMA radar TO radar_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA radar TO radar_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA radar TO radar_app;
ALTER ROLE radar_app SET search_path TO radar, pg_catalog;
ALTER ROLE radar_app SET statement_timeout TO '20s';
ALTER ROLE radar_app SET lock_timeout TO '5s';
ALTER ROLE radar_app CONNECTION LIMIT 3;
COMMIT;
SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, has_schema_privilege('radar_app','radar','USAGE') AS pode_usar_schema, has_schema_privilege('radar_app','radar','CREATE') AS pode_criar_tabelas, (SELECT count(*) FROM pg_tables WHERE schemaname='radar' AND has_table_privilege('radar_app', format('%I.%I',schemaname,tablename), 'SELECT') AND has_table_privilege('radar_app', format('%I.%I',schemaname,tablename), 'INSERT') AND has_table_privilege('radar_app', format('%I.%I',schemaname,tablename), 'UPDATE') AND has_table_privilege('radar_app', format('%I.%I',schemaname,tablename), 'DELETE')) AS tabelas_com_acesso FROM pg_roles WHERE rolname='radar_app';

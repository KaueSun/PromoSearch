-- Execute no SQL Editor do projeto Supabase Free escolhido.
-- Não contém senhas. Login e senha do papel devem ser definidos no painel,
-- com um valor aleatório privado, ou com psql \password radar_app.
-- Este schema não deve ser incluído em Settings > Data API > Exposed schemas.
CREATE ROLE radar_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE SCHEMA radar AUTHORIZATION radar_app;
REVOKE ALL ON SCHEMA radar FROM PUBLIC;
ALTER ROLE radar_app SET search_path TO radar, pg_catalog;
ALTER DEFAULT PRIVILEGES FOR ROLE radar_app IN SCHEMA radar REVOKE ALL ON TABLES FROM PUBLIC;
-- Inicie o schema com radar init-db usando a conexão do papel radar_app.
-- Não use postgres (administrador), anon ou service_role como conta da aplicação.


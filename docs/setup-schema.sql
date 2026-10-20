-- PromoSearch: estrutura privada sem senhas, tokens ou dados ficticios.

-- Apenas tabelas e indices. Nenhum usuario de acesso externo e criado.

BEGIN;

CREATE SCHEMA IF NOT EXISTS radar AUTHORIZATION postgres;

REVOKE ALL ON SCHEMA radar FROM PUBLIC, anon, authenticated, service_role;

SET LOCAL search_path TO radar, pg_catalog;

CREATE TABLE IF NOT EXISTS alerts (
	id VARCHAR(32) NOT NULL,
	listing VARCHAR(200) NOT NULL,
	product_id VARCHAR(64) NOT NULL,
	condition VARCHAR(20) NOT NULL,
	basis VARCHAR(30) NOT NULL,
	price INTEGER NOT NULL,
	at BIGINT NOT NULL,
	state VARCHAR(30) NOT NULL,
	message_id VARCHAR(100),
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_alert_listing ON alerts (listing, at);

CREATE TABLE IF NOT EXISTS leases (
	name VARCHAR(30) NOT NULL,
	owner VARCHAR(32) NOT NULL,
	until BIGINT NOT NULL,
	PRIMARY KEY (name)
);

CREATE TABLE IF NOT EXISTS manual_submissions (
	id VARCHAR(64) NOT NULL,
	at BIGINT NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
	provider VARCHAR(30) NOT NULL,
	ciphertext TEXT NOT NULL,
	PRIMARY KEY (provider)
);

CREATE TABLE IF NOT EXISTS products (
	id VARCHAR(64) NOT NULL,
	spec JSON NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS runs (
	id VARCHAR(32) NOT NULL,
	at BIGINT NOT NULL,
	state VARCHAR(30) NOT NULL,
	counts JSON NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS schema_version (
	version SERIAL NOT NULL,
	PRIMARY KEY (version)
);

CREATE TABLE IF NOT EXISTS watches (
	listing VARCHAR(60) NOT NULL,
	sku VARCHAR(150) NOT NULL,
	signature VARCHAR(64) NOT NULL,
	enabled BOOLEAN NOT NULL,
	PRIMARY KEY (listing)
);

CREATE TABLE IF NOT EXISTS listings (
	id VARCHAR(200) NOT NULL,
	product_id VARCHAR(64) NOT NULL,
	seller VARCHAR(150) NOT NULL,
	data JSON NOT NULL,
	seen BIGINT NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE IF NOT EXISTS observations (
	id SERIAL NOT NULL,
	listing VARCHAR(200) NOT NULL,
	product_id VARCHAR(64) NOT NULL,
	seller VARCHAR(150) NOT NULL,
	at BIGINT NOT NULL,
	bucket BIGINT NOT NULL,
	price INTEGER NOT NULL,
	shipping INTEGER,
	basis VARCHAR(30) NOT NULL,
	condition VARCHAR(20) NOT NULL,
	usable BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (listing, bucket),
	FOREIGN KEY(listing) REFERENCES listings (id)
);

CREATE INDEX IF NOT EXISTS ix_equivalent ON observations (product_id, at);

CREATE INDEX IF NOT EXISTS ix_history ON observations (listing, at);

DO $check$ BEGIN IF EXISTS (SELECT 1 FROM radar.schema_version WHERE version <> 1) THEN RAISE EXCEPTION 'Versao de schema incompativel'; END IF; END $check$;

INSERT INTO radar.schema_version(version) VALUES (1) ON CONFLICT DO NOTHING;

INSERT INTO radar.leases(name, owner, until) VALUES ('monitor', '', 0) ON CONFLICT DO NOTHING;

REVOKE ALL ON ALL TABLES IN SCHEMA radar FROM PUBLIC, anon, authenticated, service_role;

REVOKE ALL ON ALL SEQUENCES IN SCHEMA radar FROM PUBLIC, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA radar REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA radar REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated, service_role;

COMMIT;

SELECT table_name FROM information_schema.tables WHERE table_schema = 'radar' ORDER BY table_name;

-- =====================================================================
-- 01_setup_catalog_schemas_volumes.sql
-- Healthcare HL7 v2 + FHIR Lakehouse: one-time environment setup
--
-- Creates:
--   catalog  health
--   schemas  bronze (raw), silver (cleaned, conformed, de-identified),
--            gold (star schema for analytics)
--   volumes  health.bronze.fhir_raw  - Synthea FHIR R4 bundles (JSON)
--            health.bronze.hl7_raw   - legacy HL7 v2 ADT feed (.hl7)
--
-- Safe to re-run: every statement uses IF NOT EXISTS.
-- =====================================================================

-- 1. Catalog ----------------------------------------------------------
CREATE CATALOG IF NOT EXISTS health
COMMENT 'Synthetic healthcare data: HL7 v2 ADT feed and FHIR R4 export consolidated into a de-identified star schema';

USE CATALOG health;

-- 2. Schemas (medallion layers) ---------------------------------------
CREATE SCHEMA IF NOT EXISTS bronze
COMMENT 'Raw data exactly as received, plus load audit columns. Contains direct identifiers.';

CREATE SCHEMA IF NOT EXISTS silver
COMMENT 'Parsed, cleaned and conformed data. Direct identifiers removed; patient IDs hashed.';

CREATE SCHEMA IF NOT EXISTS gold
COMMENT 'Star schema and views for analytics and dashboards. De-identified.';

-- 3. Volumes for raw files ---------------------------------------------
CREATE VOLUME IF NOT EXISTS bronze.fhir_raw
COMMENT 'Synthea FHIR R4 bundles: one JSON file per patient, plus hospital and practitioner files';

CREATE VOLUME IF NOT EXISTS bronze.hl7_raw
COMMENT 'Legacy hospital HL7 v2.5.1 ADT feed: one file per month, one message per line';

-- 4. Validation ---------------------------------------------------------
SHOW SCHEMAS IN health;          -- expect bronze, silver, gold (plus default, information_schema)
SHOW VOLUMES IN health.bronze;   -- expect fhir_raw, hl7_raw

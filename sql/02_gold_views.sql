-- =====================================================================
-- 02_gold_views.sql
-- Reporting views on the gold star schema. The dashboard reads from these.
-- Run after notebooks/06_gold_star_schema.
-- =====================================================================

USE CATALOG health;

-- One row per encounter, joined to every dimension
CREATE OR REPLACE VIEW gold.vw_encounter_analytics
COMMENT 'Encounters joined to patient, facility and date dimensions, with age at admission. De-identified.'
AS
SELECT
  f.encounter_key,
  f.patient_key,
  f.encounter_class,
  f.encounter_class_name,
  f.type_display                            AS encounter_type,
  f.admit_ts,
  f.discharge_ts,
  f.length_of_stay_hours,
  f.length_of_stay_hours / 24.0             AS length_of_stay_days,
  f.readmitted_within_30d,
  f.had_transfer,
  f.source_systems,
  p.sex,
  p.birth_year,
  year(f.admit_ts) - p.birth_year           AS age_at_admission,
  CASE
    WHEN year(f.admit_ts) - p.birth_year < 18 THEN '0-17'
    WHEN year(f.admit_ts) - p.birth_year < 40 THEN '18-39'
    WHEN year(f.admit_ts) - p.birth_year < 65 THEN '40-64'
    ELSE '65+'
  END                                       AS age_group,
  p.zip3,
  p.state                                   AS patient_state,
  fac.facility_name,
  fac.city                                  AS facility_city,
  d.full_date                               AS admit_date,
  d.year                                    AS admit_year,
  d.year_quarter                            AS admit_quarter,
  d.month_start_date                        AS admit_month,
  d.day_name                                AS admit_day
FROM gold.fact_encounter f
JOIN gold.dim_patient  p   ON p.patient_key   = f.patient_key
JOIN gold.dim_facility fac ON fac.facility_key = f.facility_key
JOIN gold.dim_date     d   ON d.date_key      = f.admit_date_key;

-- One row per encounter and diagnosis, for "top diagnoses" analysis
CREATE OR REPLACE VIEW gold.vw_encounter_diagnoses
COMMENT 'Encounter diagnoses with SNOMED CT names, encounter class and admission year.'
AS
SELECT
  b.encounter_key,
  b.diagnosis_code,
  dx.diagnosis_name,
  f.encounter_class_name,
  year(f.admit_ts) AS admit_year,
  f.source_systems
FROM gold.fact_encounter_diagnosis b
JOIN gold.dim_diagnosis  dx ON dx.diagnosis_code = b.diagnosis_code
JOIN gold.fact_encounter f  ON f.encounter_key   = b.encounter_key;

-- Checks
SELECT COUNT(*) AS encounters FROM gold.vw_encounter_analytics;          -- expect 5,087
SELECT COUNT(*) AS encounter_diagnoses FROM gold.vw_encounter_diagnoses; -- about 3,400

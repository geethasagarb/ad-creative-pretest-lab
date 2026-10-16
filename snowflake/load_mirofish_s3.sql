-- =====================================================================
-- ad-creative-pretest-lab | Step 5: load MiroFish simulation output from S3
-- Pattern: external stage -> INFER_SCHEMA table -> COPY INTO
-- Repo path: snowflake/load_mirofish_s3.sql
-- S3 layout (one folder per table):
--   s3://geetha-adlab-raw-2026/mirofish/reactions/mirofish_reactions.csv
--   s3://geetha-adlab-raw-2026/mirofish/personas/personas.csv
-- Safe to rerun: tables use IF NOT EXISTS, and COPY skips already-loaded files.
-- =====================================================================

-- ---------------------------------------------------------------------
-- PART A (admin, once): allow the integration to read the new folder
-- ---------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

ALTER INTEGRATION S3_ADLAB_INT SET STORAGE_ALLOWED_LOCATIONS = (
  's3://your-bucket-name/kaggle_fb_ads/',
  's3://your-bucket-name/mirofish/'
);

-- ---------------------------------------------------------------------
-- PART B: load (LOADER role)
-- ---------------------------------------------------------------------
USE ROLE LOADER;
USE WAREHOUSE LOADING_WH;
USE SCHEMA RAW.MIROFISH;

CREATE OR REPLACE FILE FORMAT CSV_HEADER_FORMAT
  TYPE = CSV
  PARSE_HEADER = TRUE
  RECORD_DELIMITER = '\r\n'                 -- Python-written files end lines in \r\n
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  EMPTY_FIELD_AS_NULL = TRUE
  ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE;   -- tables have 2 extra audit columns

CREATE OR REPLACE STAGE MIROFISH_S3_STAGE
  URL = 's3://your-bucket-name/mirofish/'
  STORAGE_INTEGRATION = S3_ADLAB_INT;

LIST @MIROFISH_S3_STAGE;   -- expect 2 files

-- 1. Simulated reactions (one row per post / quote / repost / comment)
CREATE TABLE IF NOT EXISTS SIM_REACTIONS
  USING TEMPLATE (
    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
    FROM TABLE(INFER_SCHEMA(
      LOCATION => '@MIROFISH_S3_STAGE/reactions/',
      FILE_FORMAT => 'CSV_HEADER_FORMAT'))
  );

ALTER TABLE SIM_REACTIONS ADD COLUMN IF NOT EXISTS _SOURCE_FILE VARCHAR;
ALTER TABLE SIM_REACTIONS ADD COLUMN IF NOT EXISTS _LOADED_AT TIMESTAMP_LTZ;

COPY INTO SIM_REACTIONS
FROM @MIROFISH_S3_STAGE/reactions/
FILE_FORMAT = (FORMAT_NAME = 'CSV_HEADER_FORMAT')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
INCLUDE_METADATA = (_SOURCE_FILE = METADATA$FILENAME, _LOADED_AT = METADATA$START_SCAN_TIME)
ON_ERROR = 'ABORT_STATEMENT';

-- 2. Persona roster (age band, gender, job, ...)
CREATE TABLE IF NOT EXISTS PERSONAS
  USING TEMPLATE (
    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
    FROM TABLE(INFER_SCHEMA(
      LOCATION => '@MIROFISH_S3_STAGE/personas/',
      FILE_FORMAT => 'CSV_HEADER_FORMAT'))
  );

ALTER TABLE PERSONAS ADD COLUMN IF NOT EXISTS _SOURCE_FILE VARCHAR;
ALTER TABLE PERSONAS ADD COLUMN IF NOT EXISTS _LOADED_AT TIMESTAMP_LTZ;

COPY INTO PERSONAS
FROM @MIROFISH_S3_STAGE/personas/
FILE_FORMAT = (FORMAT_NAME = 'CSV_HEADER_FORMAT')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
INCLUDE_METADATA = (_SOURCE_FILE = METADATA$FILENAME, _LOADED_AT = METADATA$START_SCAN_TIME)
ON_ERROR = 'ABORT_STATEMENT';

-- ---------------------------------------------------------------------
-- PART C: checks
-- ---------------------------------------------------------------------
SELECT COUNT(*) FROM SIM_REACTIONS;   -- expect 111
SELECT COUNT(*) FROM PERSONAS;        -- expect 48

-- Every author should match a persona (expect 0 rows)
SELECT DISTINCT r."agent_name"
FROM SIM_REACTIONS r
LEFT JOIN PERSONAS p ON p."full_name" = r."agent_name"
WHERE p."full_name" IS NULL;

-- Reactions per segment (expect 8 rows)
SELECT p."age_band", p."gender", COUNT(*) AS reactions
FROM SIM_REACTIONS r
JOIN PERSONAS p ON p."full_name" = r."agent_name"
WHERE r."is_seed_post" = FALSE AND r."reaction_type" <> 'repost'
GROUP BY 1, 2
ORDER BY 1, 2;

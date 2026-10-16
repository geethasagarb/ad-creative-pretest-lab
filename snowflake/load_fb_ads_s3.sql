-- =====================================================================
-- ad-creative-pretest-lab | Step 2: load Kaggle FB ads CSV from S3
-- Pattern: storage integration -> external stage -> INFER_SCHEMA table -> COPY INTO
-- Repo path: snowflake/load_fb_ads_s3.sql
-- Replace placeholders locally; keep them as placeholders in the public repo.
-- =====================================================================

-- ---------------------------------------------------------------------
-- PART A: secure link to AWS (admin job, run once)
-- ---------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

CREATE STORAGE INTEGRATION IF NOT EXISTS S3_ADLAB_INT
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<AWS_ACCOUNT_ID>:role/snowflake-adlab-role'
  STORAGE_ALLOWED_LOCATIONS = ('s3://<your-bucket-name>/');

DESC INTEGRATION S3_ADLAB_INT;
-- Copy STORAGE_AWS_IAM_USER_ARN + STORAGE_AWS_EXTERNAL_ID into the AWS role's trust policy

GRANT USAGE ON INTEGRATION S3_ADLAB_INT TO ROLE LOADER;

-- ---------------------------------------------------------------------
-- PART B: load (LOADER role)
-- ---------------------------------------------------------------------
USE ROLE LOADER;
USE WAREHOUSE LOADING_WH;
USE SCHEMA RAW.KAGGLE_FB_ADS;

CREATE OR REPLACE FILE FORMAT CSV_HEADER_FORMAT
  TYPE = CSV
  PARSE_HEADER = TRUE
  RECORD_DELIMITER = '\r'          -- this file uses old Mac (CR) line endings
  FIELD_OPTIONALLY_ENCLOSED_BY = '"';

CREATE STAGE IF NOT EXISTS FB_ADS_S3_STAGE
  URL = 's3://<your-bucket-name>/kaggle_fb_ads/'
  STORAGE_INTEGRATION = S3_ADLAB_INT;

LIST @FB_ADS_S3_STAGE;             -- file visible = AWS link works

-- Table built automatically from the file header (scales to many tables)
CREATE TABLE IF NOT EXISTS CONVERSIONS
  USING TEMPLATE (
    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
    FROM TABLE(INFER_SCHEMA(
      LOCATION => '@FB_ADS_S3_STAGE',
      FILE_FORMAT => 'CSV_HEADER_FORMAT'))
  );

COPY INTO CONVERSIONS
FROM @FB_ADS_S3_STAGE
FILE_FORMAT = (FORMAT_NAME = 'CSV_HEADER_FORMAT')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
ON_ERROR = 'ABORT_STATEMENT';      -- any bad row = load nothing
-- Re-running COPY skips already-loaded files (tracked by MD5), so no duplicates.

-- ---------------------------------------------------------------------
-- PART C: checks
-- Note: INFER_SCHEMA kept the header's exact case, so names need double quotes.
-- The dbt staging model will rename them to clean uppercase.
-- ---------------------------------------------------------------------
SELECT COUNT(*) AS row_count FROM CONVERSIONS;   -- expect 1143

SELECT "gender", "age", COUNT(*) AS ads,
       ROUND(SUM("Spent"), 2) AS total_spent,
       SUM("Approved_Conversion") AS approved
FROM CONVERSIONS
GROUP BY "gender", "age"
ORDER BY "gender", "age";                        -- expect 8 rows

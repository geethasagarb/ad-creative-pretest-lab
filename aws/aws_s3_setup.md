# AWS side: S3 bucket + IAM role for Snowflake

Placeholders to replace:
- `username-adlab-raw-2026` → your bucket name (must be globally unique, lowercase, no spaces)
- `<AWS_ACCOUNT_ID>` → your 12-digit AWS account ID (top right menu in the AWS console)

---

## Part 1: Create the bucket and upload the file
1. AWS console → **S3** → **Create bucket**
2. Name: `geetha-adlab-raw-2026`
3. Region: **US East (Ohio) us-east-2** (same region as your Snowflake account, so no transfer fees)
4. Keep **Block all public access** turned ON. Snowflake reads through a role, not a public link.
5. Create bucket → open it → **Create folder** named `kaggle_fb_ads`
6. Open the folder → **Upload** → `KAG_conversion_data.csv`

Folder-per-source in the bucket mirrors the schema-per-source in Snowflake.

## Part 2: Create a read-only policy
1. AWS console → **IAM** → **Policies** → **Create policy** → **JSON** tab
2. Paste this (replace the bucket name in both places):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:GetObjectVersion"],
      "Resource": "arn:aws:s3:::username-adlab-raw-2026/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::username-adlab-raw-2026"
    }
  ]
}
```
3. Name it `snowflake-adlab-read` → Create policy

Read-only on purpose: Snowflake only needs to list and read files, so that is all it gets (least privilege again).

## Part 3: Create the role Snowflake will use
1. IAM → **Roles** → **Create role**
2. Trusted entity: **AWS account** → **This account**
3. Tick **Require external ID** → enter `0000` for now (temporary; fixed in Part 4)
4. Next → attach `snowflake-adlab-read` → Next
5. Role name: `snowflake-adlab-role` → Create role
6. Open the role and **copy its ARN**. It looks like `arn:aws:iam::<AWS_ACCOUNT_ID>:role/snowflake-adlab-role`

Now run **Part A** of `load_fb_ads_s3.sql` in Snowflake, using this ARN. The `DESC INTEGRATION` output gives you two values for Part 4.

## Part 4: Let Snowflake in (update the trust policy)
From the `DESC INTEGRATION` output, copy:
- `STORAGE_AWS_IAM_USER_ARN`
- `STORAGE_AWS_EXTERNAL_ID`

1. IAM → Roles → `snowflake-adlab-role` → **Trust relationships** → **Edit trust policy**
2. Replace everything with this, pasting your two values:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "AWS": "<STORAGE_AWS_IAM_USER_ARN>" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": { "sts:ExternalId": "<STORAGE_AWS_EXTERNAL_ID>" }
      }
    }
  ]
}
```
3. Update policy.

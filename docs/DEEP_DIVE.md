# Creative Pretest Lab: Technical Deep Dive

This document explains **exactly what was built, why each choice was made, what went wrong along the way, and how to make it better**. It's written for an engineer or analyst who wants to understand, reproduce, or extend the project.

> **One-line summary:** 48 AI personas reacted to 4 ad ideas in a local multi-agent simulation. The output landed in S3, loaded into Snowflake, and was modeled in dbt, where Snowflake Cortex tagged each reaction. A Streamlit app then compares the simulated audiences with real 2017 ad performance.

---

## Contents

1. [Business question](#1-business-question)
2. [End-to-end architecture](#2-end-to-end-architecture)
3. [Stage 1: Simulation (MiroFish)](#3-stage-1-simulation-mirofish)
4. [Stage 2: Landing (AWS S3)](#4-stage-2-landing-aws-s3)
5. [Stage 3: Loading (Snowflake RAW)](#5-stage-3-loading-snowflake-raw)
6. [Stage 4: Transformation (dbt + Cortex)](#6-stage-4-transformation-dbt--cortex)
7. [Stage 5: Serving (Streamlit)](#7-stage-5-serving-streamlit)
8. [Security, governance and cost](#8-security-governance-and-cost)
9. [What the data actually says](#9-what-the-data-actually-says)
10. [Bias and validity](#10-bias-and-validity)
11. [Problems hit and how they were fixed](#11-problems-hit-and-how-they-were-fixed)
12. [How to make it better (prioritised)](#12-how-to-make-it-better-prioritised)
13. [What not to do](#13-what-not-to-do)
14. [Reproduce it](#14-reproduce-it)

---

## 1. Business question

A (fictional) home-workout app, **Stride Studio**, has four ad ideas and one launch budget:

| Code | Ad | Angle |
|---|---|---|
| A | Free Trial | Offer-led: "Try free for 7 days" |
| B | Real Members | Social proof: "50,000 people stopped paying for a gym they never used" |
| C | 20 Minutes for You | Emotional: "The kids are asleep. You have 20 minutes." |
| D | 30-Day Challenge | Urgency/goal: "The 30-Day Reset starts Monday" |

**Questions:** Which ad creates the most intent to sign up? Which audience (age band × gender) should see it? And do the simulated audiences behave like real ones?

**Where this sits in real marketing work:** this is **concept pretesting**, done before launch. In industry it's usually done with survey panels. AI simulation is a cheaper first filter that narrows many ideas to a few. It's **not** a replacement for live A/B testing, which measures what real people actually do.

---

## 2. End-to-end architecture

![Detailed architecture](architecture_detailed.svg)

| Layer | Technology | Role / compute | Output |
|---|---|---|---|
| Simulate | MiroFish-Offline, Ollama (Qwen 2.5 7B), Neo4j, Docker | Local Mac (16 GB) | `mirofish_reactions.csv`, `personas.csv` |
| Real source | Kaggle "Sales Conversion Optimization" | — | `KAG_conversion_data.csv` (1,143 rows) |
| Land | AWS S3 (us-east-2) | Read-only IAM role | One folder per source |
| Load | Snowflake storage integration, external stages, `COPY INTO` | `LOADER` · `LOADING_WH` | `RAW` database |
| Transform | dbt Cloud (Developer plan), Snowflake Cortex | `TRANSFORMER` · `TRANSFORMING_WH` | `ANALYTICS.PROD` (prod), `ANALYTICS.DBT_<user>` (dev) |
| Serve | Streamlit in Snowflake, plus a public Streamlit Community Cloud copy | `REPORTER` · `REPORTING_WH` | 5-chapter dashboard |

Snowflake and S3 sit in the same AWS region (**us-east-2, Ohio**), so moving data between them incurs no cross-region transfer cost.

---

## 3. Stage 1: Simulation (MiroFish)

### 3.1 What MiroFish does

[MiroFish-Offline](https://github.com/nikmcfly/MiroFish-Offline) is an English, fully local fork of MiroFish, a multi-agent "swarm" simulation engine. Given a **seed document** and a **goal**, it:

1. **Builds an ontology:** the LLM decides what kinds of entities and relationships exist in the seed.
2. **Builds GraphRAG memory:** it chunks the seed, extracts entities and links into **Neo4j**, and embeds them with `nomic-embed-text`.
3. **Generates agent personas:** one LLM call per entity writes a profile (bio, job, personality, interests).
4. **Configures the simulation:** activity rates, active hours, response delays and feed-ranking weights for each agent.
5. **Runs a dual-platform simulation:** a Twitter-style feed and a Reddit-style forum run in parallel. Each round equals one simulated hour, and active agents post, comment, quote, repost or like.

Output lands in two SQLite databases (`twitter_simulation.db`, `reddit_simulation.db`) plus JSONL action logs.

### 3.2 Local stack

| Component | Version / setting | Why |
|---|---|---|
| LLM | `qwen2.5:7b` via Ollama | Fits a 16 GB Mac. Reasoning models like DeepSeek R1 add "thinking" text that breaks structured output, and 3B models can't hold a persona. |
| Embeddings | `nomic-embed-text` | Small, local, used for memory search |
| Graph DB | Neo4j 5.15 Community in Docker | MiroFish-Offline's memory store |
| Python | 3.11 in a `.venv` | A dependency (`camel-oasis`) doesn't support 3.12 |
| `mcp` package | pinned `<2` | `mcp` 2.x removed the `FastMCP` import that the engine uses |
| Ollama | `OLLAMA_NUM_PARALLEL=1` | Parallel requests from two platforms pushed memory past 16 GB and crashed the Mac |

**No simulation data leaves the laptop.** That matters if a real brief or product plan were used as the seed.

### 3.3 Designing the seed (what worked and what didn't)

| Version | Approach | Result |
|---|---|---|
| v1 | Described the audience as **categories** ("office worker, careful with spending, men…") | ❌ The 7B model turned every phrase into an account: agents named "price", "men", "Age bands", plus fake brand and media accounts. 45 agents, almost none real people. |
| v2 | 24 **named people**, each with age, gender, job, family, fitness and money attitude written into one line | Better, but only 3 per segment |
| v3 | **48 people generated by script** (`mirofish/generate_seed.py`): 6 per segment, with fitness, money, schedule and family rotated so every trait is balanced | ✅ All 48 named people became agents, plus 14 non-person entities (ads, buttons, brand) that were muted or filtered out |

**Lesson:** small models take a seed literally. Describe **individuals**, not categories, and generate them with code so the mix is balanced and reproducible (fixed random seed 42).

### 3.4 Fixing the agent configuration

MiroFish's auto-generated config had problems that would have biased results, so `simulation_config.json` was edited before the run (the original is kept as `simulation_config.backup.json`):

| Problem found | Fix |
|---|---|
| 6 agents (all aged 45–49, 5 of them women) had posting and commenting rates of **0**, so they would never react | All 48 people set to the same rates: 0.1 posts and 0.2 comments per hour |
| Rates varied about 20× between batches of agents (an artifact of how the LLM generated them, not of persona traits) | Equalised, as above |
| Active only 19:00–22:00 | Widened to 08:00–22:00 |
| Non-person entities (brand, "teenagers", "young children", ad features) set to post | Muted |
| Time model based on a Chinese work schedule | Left as is (minor), and noted |

### 3.5 What was actually captured

The planned run was 70 rounds. The Mac ran out of memory at about **round 12**. The partial output was backed up and used:

| Item | Count |
|---|---|
| Rows exported | 111 (59 Twitter posts/quotes/reposts, 52 Reddit posts/comments) |
| Seed posts (MiroFish's opening posts, excluded) | 12 |
| Reposts (no text of their own, excluded from text analysis) | 11 |
| **Text reactions analysed** | **88**, from 46 of the 48 people, at most 3 per person |

`mirofish/export_reactions.py` flattens both SQLite databases into one CSV, maps each agent to its persona name, assigns each row a round number from the action logs, and flags seed posts.

---

## 4. Stage 2: Landing (AWS S3)

```
s3://<bucket>/
├── kaggle_fb_ads/KAG_conversion_data.csv
└── mirofish/
    ├── reactions/mirofish_reactions.csv
    └── personas/personas.csv
```

- **One folder per source and per table.** New simulation runs drop new files into `reactions/`, and `COPY INTO` loads only files it hasn't seen.
- **Block public access is on.** Snowflake reads through an IAM role, not a public link.
- **IAM policy:** `s3:GetObject`, `s3:GetObjectVersion`, `s3:ListBucket`, `s3:GetBucketLocation` only. That's read-only, the minimum Snowflake needs.
- **Trust policy:** only Snowflake's IAM user, presenting this account's **external ID**, can assume the role. No access keys are stored anywhere.

---

## 5. Stage 3: Loading (Snowflake RAW)

**Pattern:** storage integration → external stage → `INFER_SCHEMA` → `CREATE TABLE … USING TEMPLATE` → `COPY INTO … MATCH_BY_COLUMN_NAME`.

| Object | Detail |
|---|---|
| Storage integration | `S3_ADLAB_INT`, with **allowed locations per folder** (`kaggle_fb_ads/`, `mirofish/`) |
| Kaggle file format | `RECORD_DELIMITER = '\r'`, because the Kaggle file uses old Mac line endings |
| MiroFish file format | `RECORD_DELIMITER = '\r\n'` (Python-written), `ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE` (the tables have 2 extra audit columns) |
| Tables | `RAW.KAGGLE_FB_ADS.CONVERSIONS`, `RAW.MIROFISH.SIM_REACTIONS`, `RAW.MIROFISH.PERSONAS` |
| Audit columns | `_SOURCE_FILE`, `_LOADED_AT` via `INCLUDE_METADATA` (MiroFish tables) |
| Error handling | `ON_ERROR = 'ABORT_STATEMENT'`, so a bad file loads nothing (no half-loads) |
| Idempotency | `COPY INTO` tracks loaded files, so reruns don't duplicate rows |

**Why `INFER_SCHEMA`:** hand-writing `CREATE TABLE` doesn't scale across many sources. Inferring from the file header is the pattern teams use with config-driven loaders. The trade-off is that column names keep the file's exact case, so staging models quote them (`"Spent"`) and rename them cleanly.

**Checks run after loading:** 1,143 Kaggle rows · 111 reactions · 48 personas · **0 reaction authors without a matching persona** · all 8 segments present.

---

## 6. Stage 4: Transformation (dbt + Cortex)

### 6.1 Model layers

![dbt lineage](dbt_lineage.png)

| Layer | Model | Materialisation | Logic |
|---|---|---|---|
| Staging | `stg_kaggle_fb_ads__conversions` | view | Rename quoted columns (`"Spent"` → `spend_usd`, `"age"` → `age_band`) |
| Staging | `stg_mirofish__reactions` | view | Rename, keep every row including seed posts (filtering is business logic, so it isn't done here) |
| Staging | `stg_mirofish__personas` | view | Rename, `male/female` → `M/F` to match Kaggle |
| Intermediate | `int_mirofish__reactions_enriched` | **table** | Drop seed posts and reposts, then call Cortex 3× per row (below) |
| Mart | `mart_fb_ads__segment_performance` | table | Real 2017 results per segment: CTR %, cost per approved conversion |
| Mart | `mart_creative_pretest__segment_ad` | table | 8 segments × 4 ads (32 rows): simulated metrics beside the real benchmark |

### 6.2 Cortex enrichment

| Output column | Cortex function | Values |
|---|---|---|
| `sentiment_score` | `SNOWFLAKE.CORTEX.SENTIMENT` | −1 … +1 |
| `ad_mentioned` | `SNOWFLAKE.CORTEX.CLASSIFY_TEXT`, with a description per label | A / B / C / D / general |
| `intent` | `CLASSIFY_TEXT` | will_try / curious / not_interested / already_using |

**Guardrail:** Cortex returns `UNCLASSIFIED` when it isn't confident. The model maps any label outside the fixed list to `unclassified`, and tests enforce that list. **Never trust raw AI labels downstream.**

**Why a table, not a view:** each row costs three LLM calls. Materialising the results means dashboards read stored values instead of re-running the AI on every query.

### 6.3 Mart design choices

- **Spine (segments × ads cross join):** an ad nobody mentioned in a segment shows **0 reactions**, instead of disappearing from the chart.
- **Null, not zero:** `sim_will_try / NULLIF(sim_reactions, 0)` gives **no rate** when there's no data, rather than a fake 0%.
- **`is_low_sample` flag:** fewer than 5 reactions. The dashboard greys these out.
- **The real benchmark joins on segment only.** The Kaggle ads aren't these four creatives, so real metrics repeat across ads within a segment and are never blended with simulated metrics.

### 6.4 Tests (25)

`unique` / `not_null` on every key · `accepted_values` on gender, age band, platform, reaction type, ad label, intent · `relationships` (every reaction's author exists in personas) · `not_null` on `real_ctr_pct` (proves the simulated-to-real join matched).

### 6.5 Dev → prod workflow

```
feature branch → dbt build in ANALYTICS.DBT_<developer> → pull request → review → merge to main
→ "Production build" deploy job (dbt build) → ANALYTICS.PROD → dashboard
```

- Development and production use **the same code and separate schemas**. The dashboard never reads a developer sandbox.
- The production job is **manual**. The data is a one-off snapshot, and a daily schedule would only re-run Cortex and spend credits.
- This is the **CD** half. There's **no CI job yet** (one that builds and tests each pull request automatically before merge).

---

## 7. Stage 5: Serving (Streamlit)

- **Streamlit in Snowflake** lives in `ANALYTICS.APPS`, is owned by `REPORTER`, runs on `REPORTING_WH`, and reads `ANALYTICS.PROD` only.
- **The public copy** runs on Streamlit Community Cloud. The **same app file** detects that there's no Snowflake session and reads a **CSV snapshot** of the two tables it uses, so it keeps working after the Snowflake trial ends.
- **It's built as a story, not a wall of charts:** 1 · problem → 2 · which ad? → 3 · for whom? → 4 · reality check → 5 · decision. Every chart carries a **source line** saying whether its data is simulated or real.
- Snowflake's classic dashboards are marked **deprecated**, which is why Streamlit was chosen.

---

## 8. Security, governance and cost

| Area | Implementation |
|---|---|
| Roles | `LOADER` (write RAW) · `TRANSFORMER` (read RAW, own ANALYTICS) · `REPORTER` (read ANALYTICS, build apps in `APPS`) |
| Warehouses | One per job, XSMALL, 60-second auto-suspend, auto-resume |
| Cost cap | Resource monitor: 20 credits/month, notify at 75%, suspend at 100% |
| Cloud access | IAM role + external ID, read-only, no stored keys |
| AI data boundary | Local LLM for simulation, Cortex inside Snowflake for enrichment, no external AI APIs |
| Public repo | Placeholders for account ID, bucket and ARNs. The full git history was scanned for secrets, with none found. |
| Production identity | ⚠️ The dbt prod job uses a **personal user**. In a real team it should be a **service user with key-pair auth**. |

---

## 9. What the data actually says

### 9.1 Which ad? (with honest uncertainty)

| Ad | Reactions | Would try | 95% interval (Wilson) |
|---|---|---|---|
| D · 30-Day Challenge | 39 | 41% | 27–57% |
| C · 20 Minutes for You | 35 | 29% | 16–45% |
| A · Free Trial | 5 | 40% | 12–77% |
| B · Real Members | 3 | 0% | 0–56% |

**Reading it correctly:** D has the highest point estimate, but **its interval overlaps heavily with C's**, so this run **does not prove D beats C**. A and B intervals are so wide they're uninformative. The honest call is: **D and C are front-runners, and A and B are untested.**

### 9.2 Intent mix (all 88 reactions)

already_using 40 · will_try 29 · curious 17 · not_interested 1 · unclassified 1.

### 9.3 Real benchmark (2017)

Cost per approved conversion rises with age, and women cost more than men in every band: from **$25.55 (men 30–34)** to **$119.94 (women 45–49)**.

### 9.4 Simulation vs reality

The simulation **agrees at the extremes**: young men are both among the most receptive simulated segments and the cheapest real one, while women 45–49 are among the least receptive and the most expensive. It **disagrees in the middle**: men 45–49 look keen in the simulation but are costly in reality. With about 10 reactions per segment, this is a hint, not a validation.

---

## 10. Bias and validity

| Bias | Evidence | Effect | Mitigation |
|---|---|---|---|
| Over-positivity | 1 negative of 88; sentiment ≈ 0.7 everywhere | Sentiment can't separate ads | Add sceptical personas, use intent rather than sentiment, try a larger model |
| Invented experience | 45% "already using" | Inflates intent | Instruct agents that the product is new; filter `already_using` |
| Exposure | Seed posts favoured C and D (74 vs 8 reactions) | A and B under-measured | One opening post per ad; randomise order |
| Herding | "Let's support each other" replies | Opinions converge | Lower echo-chamber settings; analyse first reactions separately from replies |
| Single model | Similar voice across personas | Low variance | Repeat runs, other models, varied temperature |
| Stereotypes | Women framed around parenting | Segment results reflect model priors | Specify more persona traits explicitly; audit persona bios |
| Labelling error | `unclassified`; subjective intent labels | Noise in metrics | Hand-label about 50 rows and measure Cortex agreement |
| Benchmark mismatch | 2017, other ads, segment-level only | Weak validation | Compare against a small real survey or past campaign for the same product |

**Validity statement:** results are suitable for **ranking ideas and choosing what to test live**, not for forecasting conversion rates or allocating a full budget.

---

## 11. Problems hit and how they were fixed

| Problem | Root cause | Fix |
|---|---|---|
| Snowflake: `duplicated columns … line 0` | Kaggle CSV used old Mac `\r` line endings, so the file read as one line | `RECORD_DELIMITER = '\r'` |
| Queries needed quoted lowercase columns | `INFER_SCHEMA` keeps header case | Renamed in staging |
| `DESC INTEGRATION` said "does not exist" | Integration was never created under `ACCOUNTADMIN` | Recreated as admin |
| "Location not allowed by integration" | Allowed locations covered only `kaggle_fb_ads/` | Added `mirofish/`; recreated the stage (`IF NOT EXISTS` doesn't update a URL) |
| Files uploaded to a second bucket | Created a bucket instead of a folder | Moved files into the original bucket, deleted the extra |
| COPY: column count mismatch (14 vs 16) | Audit columns added to the table | `ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE` (matching is by name) |
| `dbt run` said "Nothing to do" | Selector didn't match the model name | `--select staging` / `path:` selectors |
| New tests not found | dbt partial-parse cache missed a new YAML | `--no-partial-parse` |
| Cortex test failed | `UNCLASSIFIED` label not in the accepted list | Mapping guardrail + `unclassified` allowed |
| CTR showed 0.0001 everywhere | Rounded a tiny ratio to 4 decimals | Stored as a percent (`ctr_pct`) |
| MiroFish: `cannot import name 'FastMCP'` | `mcp` 2.3.0 installed | `pip install "mcp<2"` in the project venv |
| Wrong Python environment | Anaconda `(base)` active, not `.venv` | Called `.venv/bin/pip` and `.venv/bin/python` directly |
| Mac ran out of memory, then crashed | Browser (13 GB) + Ollama parallel requests (13 GB) on 16 GB RAM | Closed the browser, `OLLAMA_NUM_PARALLEL=1`, backed up partial output |
| Public app header covered the title | Streamlit Cloud's top bar plus reduced padding | Increased top padding; fixed theme in `.streamlit/config.toml` |

---

## 12. How to make it better (prioritised)

Effort: **S** ≈ under 1 hour · **M** ≈ a few hours · **L** ≈ a day or more.

### Priority 1: make the result trustworthy

| # | Improvement | Why | Effort |
|---|---|---|---|
| 1 | **Fair exposure:** one seed post per ad, in random order | Removes the biggest bias in this run | S |
| 2 | **3–5 repeat runs**, reported as mean ± spread | Shows whether rankings are stable or noise | M (mostly runtime) |
| 3 | **Report confidence intervals** in the mart and dashboard | Stops over-reading small differences | S |
| 4 | **Sceptical and price-sensitive personas** (about 20%) | Makes "no" a realistic answer | S |
| 5 | **Validate Cortex labels:** hand-label 50 reactions and measure agreement | Proves the AI tagging is reliable | S |
| 6 | **Run on hardware that can finish 70 rounds** (a larger machine or a GPU cloud box with the same local model) | Avoids partial runs and crashes | M |

### Priority 2: production-grade data engineering

| # | Improvement | Why | Effort |
|---|---|---|---|
| 7 | **CI job** on every pull request (`dbt build --select state:modified+`) | Catches broken code before merge | S |
| 8 | **Service user + key-pair auth** for dbt prod | No personal credentials in production | S |
| 9 | **Snowpipe auto-ingest** from S3 | New simulation files load automatically | M |
| 10 | **Personas as a dbt seed** (`seeds/personas.csv`) | Small reference data belongs in version control | S |
| 11 | **Incremental reaction model** keyed on `reaction_id` | Cortex runs only on new rows when runs accumulate | M |
| 12 | **`simulation_id` as a dimension** in marts | Compare runs and seed versions side by side | S |
| 13 | **Model contracts + `dbt docs`** (Catalog or GitHub Pages) | Documented, enforced schemas | S |
| 14 | **Source freshness** once loads are recurring | Alerts when data stops arriving | S |

### Priority 3: AI features

| # | Improvement | Why | Effort |
|---|---|---|---|
| 15 | **RAG with Cortex Search** over reaction text | Ask "why did women 35–39 prefer D?" and get grounded answers with quotes | M |
| 16 | **Theme/objection extraction** with a Cortex LLM function | Quantify objections (price, time, trust) per ad | M |
| 17 | **Try newer `AI_*` functions** (for example `AI_CLASSIFY`) and compare accuracy and cost | Better labels at a known cost | S |
| 18 | **Ground personas in real data** (RAG #1): pass segment stats into the seed | Personas start from real behaviour, not only LLM priors | M |

### Priority 4: closing the loop with reality

| # | Improvement | Why | Effort |
|---|---|---|---|
| 19 | **Small live A/B test** of the top 1–2 ads | The only real proof | L (needs budget) |
| 20 | **Calibration table:** simulated vs real per segment over time | Learn how far the simulation drifts, and correct for it | M |
| 21 | **A current benchmark** (recent campaigns or a small survey panel for the same product) | Replace the 2017 proxy | L |

---

## 13. What not to do

- **Don't report simulated rates as conversion forecasts.** "41% would try" is a relative signal, not 41% of real people.
- **Don't blend simulated and real metrics** into one score. Compare them side by side, on segment only.
- **Don't scale up personas before fixing bias.** More agents with the same exposure and positivity bias just give confident wrong answers.
- **Don't feed real customer data or confidential briefs to a cloud LLM API** without approval. Keep it local, or inside the warehouse (Cortex).
- **Don't trust raw AI labels.** Map them to a fixed list, test them, and spot-check them by hand.
- **Don't schedule Cortex models daily on static data.** It spends credits for identical results.
- **Don't point dashboards at a developer schema.** Use the production schema built by a deploy job.
- **Don't commit account IDs, bucket names, keys or `.env` files.** Use placeholders and scan history.
- **Don't run the simulation alongside heavy apps on a 16 GB machine.** Cap Ollama parallelism, or use a bigger box.

---

## 14. Reproduce it

1. **Snowflake setup:** run `snowflake/setup.sql` (warehouses, databases, roles, resource monitor).
2. **AWS:** follow `aws/aws_s3_setup.md` (bucket, read-only policy, role, trust policy).
3. **Kaggle load:** `snowflake/load_fb_ads_s3.sql`.
4. **Simulation:**
   ```bash
   python mirofish/generate_seed.py --per-cell 6      # 48 personas + seed doc
   # Run MiroFish-Offline with the seed (Ollama qwen2.5:7b, Neo4j in Docker,
   # Python 3.11 venv, mcp<2, OLLAMA_NUM_PARALLEL=1)
   python mirofish/export_reactions.py                # run inside the simulation's folder → mirofish_reactions.csv
   ```
5. **Upload** both CSVs to `s3://<bucket>/mirofish/{reactions,personas}/`, then run `snowflake/load_mirofish_s3.sql`.
6. **dbt:** `dbt build` (dev), then trigger the **Production build** job.
7. **Dashboard:** create a Streamlit app in `ANALYTICS.APPS` as `REPORTER` with `streamlit/creative_pretest_lab.py`, or run it locally/publicly with the CSV snapshot in `streamlit/data/`.

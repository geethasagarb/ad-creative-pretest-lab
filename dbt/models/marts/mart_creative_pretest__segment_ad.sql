-- Final table for the dashboard: one row per age band x gender x ad (8 x 4 = 32 rows)
-- Simulated reactions (MiroFish + Cortex) beside real 2017 Kaggle results for the same segment
{{ config(materialized='table') }}

with reactions as (

    select
        r.reaction_id,
        r.ad_mentioned as ad_code,
        r.intent,
        r.sentiment_score,
        p.age_band,
        p.gender
    from {{ ref('int_mirofish__reactions_enriched') }} r
    join {{ ref('stg_mirofish__personas') }} p
      on p.persona_name = r.persona_name
    where r.ad_mentioned in ('A_free_trial', 'B_real_members', 'C_20_minutes', 'D_30_day_challenge')

),

-- Every segment x every ad, so an ad with zero reactions shows as 0, not missing
segments as (
    select distinct age_band, gender from {{ ref('stg_mirofish__personas') }}
),

ads as (
    select column1 as ad_code, column2 as ad_name
    from (values
        ('A_free_trial',       'A: Free Trial'),
        ('B_real_members',     'B: Real Members'),
        ('C_20_minutes',       'C: 20 Minutes for You'),
        ('D_30_day_challenge', 'D: 30-Day Challenge')
    )
),

spine as (
    select s.age_band, s.gender, a.ad_code, a.ad_name
    from segments s
    cross join ads a
),

simulated as (
    select
        age_band,
        gender,
        ad_code,
        count(*)                            as sim_reactions,
        count_if(intent = 'will_try')       as sim_will_try,
        count_if(intent = 'not_interested') as sim_not_interested,
        avg(sentiment_score)                as sim_avg_sentiment
    from reactions
    group by 1, 2, 3
),

real_2017 as (
    select
        gender,
        age_band,
        impressions,
        clicks,
        spend_usd,
        approved_conversions,
        ctr_pct,
        cost_per_approved_conversion
    from {{ ref('mart_fb_ads__segment_performance') }}
)

select
    sp.age_band || '|' || sp.gender || '|' || sp.ad_code    as segment_ad_key,
    sp.age_band,
    sp.gender,
    sp.ad_code,
    sp.ad_name,

    -- Simulated (MiroFish personas, tagged by Cortex)
    coalesce(si.sim_reactions, 0)                           as sim_reactions,
    coalesce(si.sim_will_try, 0)                            as sim_will_try,
    coalesce(si.sim_not_interested, 0)                      as sim_not_interested,
    round(si.sim_will_try / nullif(si.sim_reactions, 0), 3) as sim_will_try_rate,   -- null, not 0, when no reactions
    round(si.sim_avg_sentiment, 2)                          as sim_avg_sentiment,
    coalesce(si.sim_reactions, 0) < 5                       as is_low_sample,       -- flag rates built on <5 reactions

    -- Real 2017 Kaggle results for the same segment (repeat across ads)
    r.ctr_pct                                               as real_ctr_pct,
    r.cost_per_approved_conversion                          as real_cost_per_conversion,
    round(r.approved_conversions / nullif(r.clicks, 0), 4)  as real_click_to_conversion_rate,
    r.spend_usd                                             as real_spend_usd

from spine sp
left join simulated si
  on  si.age_band = sp.age_band
  and si.gender   = sp.gender
  and si.ad_code  = sp.ad_code
left join real_2017 r
  on  r.age_band = sp.age_band
  and r.gender   = sp.gender
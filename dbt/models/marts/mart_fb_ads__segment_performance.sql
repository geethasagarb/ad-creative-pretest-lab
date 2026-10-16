with ads as (

    select * from {{ ref('stg_kaggle_fb_ads__conversions') }}

)

select
    gender,
    age_band,
    count(*)                                                        as ad_count,
    sum(impressions)                                                as impressions,
    sum(clicks)                                                     as clicks,
    round(sum(spend_usd), 2)                                        as spend_usd,
    sum(approved_conversions)                                       as approved_conversions,
    round(sum(clicks) / nullif(sum(impressions), 0) * 100, 4)       as ctr_pct,   -- percent, e.g. 0.0172 = 0.0172%
    round(sum(spend_usd) / nullif(sum(approved_conversions), 0), 2) as cost_per_approved_conversion
from ads
group by gender, age_band
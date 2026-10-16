with
    source as (select * from {{ source("kaggle_fb_ads", "conversions") }}),

    renamed as (

        select
            "ad_id" as ad_id,
            "xyz_campaign_id" as campaign_id,
            "fb_campaign_id" as fb_campaign_id,
            "age" as age_band,
            "gender" as gender,
            "interest" as interest_id,
            "Impressions" as impressions,
            "Clicks" as clicks,
            "Spent" as spend_usd,
            "Total_Conversion" as total_conversions,
            "Approved_Conversion" as approved_conversions
        from source

    )

select *
from renamed

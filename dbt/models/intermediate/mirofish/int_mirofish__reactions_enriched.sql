-- Calls the LLM once per row, so build it as a table:
-- dashboards read stored results instead of re-running AI on every query
{{ config(materialized='table') }}

with reactions as (

    select *
    from {{ ref('stg_mirofish__reactions') }}
    where not is_seed_post
      and reaction_type <> 'repost'

),

enriched as (

    select
        reaction_id,
        simulation_id,
        platform,
        reaction_type,
        persona_name,
        round_num,
        content,

        snowflake.cortex.sentiment(content) as sentiment_score,

        snowflake.cortex.classify_text(
            content,
            [
                {'label': 'A_free_trial',       'description': 'the 7-day free trial, the price, $14.99, cancel anytime'},
                {'label': 'B_real_members',     'description': 'other members, replacing a gym membership, success stories'},
                {'label': 'C_20_minutes',       'description': 'short 20-minute workouts fitting a busy schedule, kids, family time'},
                {'label': 'D_30_day_challenge', 'description': 'the 30-Day Challenge or 30-Day Reset, a plan, doing it together'},
                {'label': 'general',            'description': 'fitness or Stride Studio in general, no specific offer'}
            ],
            {'task_description': 'Which ad offer is this social media post reacting to?'}
        ):label::string as ad_mentioned_raw,

        snowflake.cortex.classify_text(
            content,
            [
                {'label': 'will_try',       'description': 'says they will sign up, join or try it'},
                {'label': 'curious',        'description': 'interested or considering, but not committed'},
                {'label': 'not_interested', 'description': 'skeptical, objects, or says no'},
                {'label': 'already_using',  'description': 'claims they already use it or did it before'}
            ],
            {'task_description': 'What is this person''s intent toward the fitness app?'}
        ):label::string as intent_raw

    from reactions

),

-- Guardrail: never trust AI labels as-is; map them onto a fixed list
final as (

    select
        reaction_id,
        simulation_id,
        platform,
        reaction_type,
        persona_name,
        round_num,
        content,
        sentiment_score,
        case
            when ad_mentioned_raw in ('A_free_trial', 'B_real_members', 'C_20_minutes', 'D_30_day_challenge', 'general')
                then ad_mentioned_raw
            else 'unclassified'
        end as ad_mentioned,
        case
            when lower(intent_raw) in ('will_try', 'curious', 'not_interested', 'already_using')
                then lower(intent_raw)
            else 'unclassified'
        end as intent
    from enriched

)

select * from final
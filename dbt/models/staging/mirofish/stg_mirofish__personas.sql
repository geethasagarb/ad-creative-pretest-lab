with source as (

    select * from {{ source('mirofish', 'personas') }}

),

renamed as (

    select
        "persona_id"        as persona_id,
        "full_name"         as persona_name,
        "age"               as age,
        "age_band"          as age_band,
        case lower("gender")
            when 'male'   then 'M'
            when 'female' then 'F'
        end                 as gender,
        "job"               as job,
        "schedule"          as work_schedule,
        "family"            as family_type,
        "fitness_level"     as fitness_level,
        "money_attitude"    as money_attitude
    from source

)

select * from renamed
with source as (

    select * from {{ source('mirofish', 'sim_reactions') }}

),

renamed as (

    select
        "reaction_id"       as reaction_id,
        "simulation_id"     as simulation_id,
        "platform"          as platform,
        "reaction_type"     as reaction_type,
        "agent_id"          as agent_id,
        "agent_name"        as persona_name,
        "handle"            as handle,
        "round_num"         as round_num,
        "parent_post_id"    as parent_post_id,
        "content"           as content,
        "num_likes"         as num_likes,
        "num_dislikes"      as num_dislikes,
        "is_seed_post"      as is_seed_post,
        _source_file        as source_file,
        _loaded_at          as loaded_at
    from source

)

select * from renamed
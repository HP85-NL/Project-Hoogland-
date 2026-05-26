with weather as (
    select * from {{ ref('stg_ext_weather_daily') }}
),

stores as (
    select * from {{ ref('stg_dim_store') }}
)

select
    w.date,
    w.region,
    w.mean_temp_c,
    w.precip_mm,
    w.wind_kmh,
    w.monthly_temp_anomaly_c,

    -- Temperature banding for analysis
    case
        when w.mean_temp_c < 0  then 'freezing'
        when w.mean_temp_c < 8  then 'cold'
        when w.mean_temp_c < 15 then 'mild'
        when w.mean_temp_c < 22 then 'warm'
        else 'hot'
    end as temp_band,

    -- Precipitation flag
    case
        when w.precip_mm = 0    then 'dry'
        when w.precip_mm < 5   then 'light_rain'
        when w.precip_mm < 15  then 'moderate_rain'
        else 'heavy_rain'
    end as precip_band,

    s.store_id,
    s.store_name,
    s.city,
    s.archetype,
    s.sqm,
    s.channel

from weather w
inner join stores s on w.region = s.region
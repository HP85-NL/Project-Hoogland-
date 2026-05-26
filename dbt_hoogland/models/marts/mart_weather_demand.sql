with sales as (
    select * from {{ ref('int_sales_enriched') }}
),

weather as (
    select * from {{ ref('int_weather_store_daily') }}
)

select
    s.date,
    s.store_id,
    s.store_name,
    s.city,
    s.region,
    s.archetype,
    s.category,
    s.subcategory,
    s.weather_sensitivity,
    s.seasonality,

    -- Sales metrics
    sum(s.net_revenue_eur)                              as net_revenue_eur,
    sum(s.gross_revenue_eur)                            as gross_revenue_eur,
    sum(s.quantity)                                     as units_sold,
    count(distinct s.transaction_id)                    as transactions,

    -- Weather context
    max(w.mean_temp_c)                                  as mean_temp_c,
    max(w.precip_mm)                                    as precip_mm,
    max(w.wind_kmh)                                     as wind_kmh,
    max(w.monthly_temp_anomaly_c)                       as monthly_temp_anomaly_c,
    max(w.temp_band)                                    as temp_band,
    max(w.precip_band)                                  as precip_band

from sales s
left join weather w
    on s.store_id = w.store_id
    and s.date    = w.date

group by
    s.date,
    s.store_id,
    s.store_name,
    s.city,
    s.region,
    s.archetype,
    s.category,
    s.subcategory,
    s.weather_sensitivity,
    s.seasonality
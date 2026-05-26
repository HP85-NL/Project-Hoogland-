with sales as (
    select * from {{ ref('int_sales_enriched') }}
),

traffic as (
    select * from {{ ref('stg_fact_traffic_daily') }}
)

select
    s.store_id,
    s.store_name,
    s.city,
    s.region,
    s.archetype,
    s.store_channel,
    s.sqm,
    s.is_outlet,
    cast(s.date as date)                              as date,

    -- Revenue
    sum(s.gross_revenue_eur)                          as gross_revenue_eur,
    sum(s.net_revenue_eur)                            as net_revenue_eur,
    sum(s.discount_amount_eur)                        as total_discount_eur,
    sum(s.quantity)                                   as units_sold,
    count(distinct s.transaction_id)                  as transactions,

    -- Basket
    sum(s.net_revenue_eur)
        / nullif(count(distinct s.transaction_id), 0) as avg_basket_eur,

    -- Margin
    sum(s.gross_margin_eur)                                 as total_margin_eur,
    sum(s.gross_margin_eur)
        / nullif(sum(s.net_revenue_eur), 0)           as margin_pct,

    -- Revenue per sqm
    sum(s.net_revenue_eur)
        / nullif(max(s.sqm), 0)                       as revenue_per_sqm_eur

from sales s
group by
    s.store_id,
    s.store_name,
    s.city,
    s.region,
    s.archetype,
    s.store_channel,
    s.sqm,
    s.is_outlet,
    cast(s.date as date)
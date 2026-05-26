with sales as (
    select * from {{ ref('stg_fact_sales') }}
),

stores as (
    select * from {{ ref('stg_dim_store') }}
),

products as (
    select * from {{ ref('stg_dim_product') }}
)

select
    s.line_id,
    s.transaction_id,
    s.date,
    s.store_id,
    st.store_name,
    st.city,
    st.region,
    st.archetype,
    st.channel        as store_channel,
    st.sqm,
    st.is_outlet,
    s.sku,
    p.product_name,
    p.brand_id,
    p.category,
    p.subcategory,
    p.gender,
    p.weather_sensitivity,
    p.seasonality,
    p.lifecycle_stage,
    s.channel         as transaction_channel,
    s.customer_id,
    s.quantity,
    s.unit_list_price_eur,
    s.discount_pct,
    s.unit_net_price_eur,
    s.gross_revenue_eur,
    s.discount_amount_eur,
    s.net_revenue_eur,
    s.cogs_eur,
    s.gross_margin_eur,
    s.promo_flag,
    s.campaign_id

from sales s
left join stores st on s.store_id = st.store_id
left join products p  on s.sku    = p.sku
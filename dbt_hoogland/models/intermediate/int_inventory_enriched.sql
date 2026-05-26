with inventory as (
    select * from {{ ref('stg_fact_inventory_weekly') }}
),

products as (
    select * from {{ ref('stg_dim_product') }}
),

stores as (
    select * from {{ ref('stg_dim_store') }}
)

select
    i.year,
    i.iso_week,
    i.store_id,
    i.sku,
    st.store_name,
    st.city,
    st.region,
    st.archetype,
    p.product_name,
    p.brand_id,
    p.category,
    p.subcategory,
    p.seasonality,
    p.lifecycle_stage,
    i.opening_stock_units,
    i.receipts_units,
    i.sales_units,
    i.closing_stock_units,
    i.weeks_of_cover,
    i.inventory_value_eur,
    i.is_stockout,
    i.is_overstock

from inventory i
left join products p on i.sku      = p.sku
left join stores  st on i.store_id = st.store_id
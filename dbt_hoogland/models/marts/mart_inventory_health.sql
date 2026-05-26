with inventory as (
    select * from {{ ref('int_inventory_enriched') }}
)

select
    year,
    iso_week,
    store_id,
    store_name,
    city,
    region,
    archetype,
    sku,
    product_name,
    brand_id,
    category,
    subcategory,
    seasonality,
    lifecycle_stage,

    -- Stock levels
    opening_stock_units,
    closing_stock_units,
    receipts_units,
    sales_units,
    inventory_value_eur,
    weeks_of_cover,

    -- Health flags
    is_stockout,
    is_overstock,

    -- Derived metrics
    case
        when is_stockout                 then 'stockout'
        when is_overstock                then 'overstock'
        when weeks_of_cover < 2          then 'at_risk'
        when weeks_of_cover > 12         then 'excess'
        else 'healthy'
    end                                  as stock_status,

    -- Lost revenue estimate (stockout days × avg weekly sales value)
    case
        when is_stockout
        then inventory_value_eur * 0.15
        else 0
    end                                  as est_lost_revenue_eur

from inventory
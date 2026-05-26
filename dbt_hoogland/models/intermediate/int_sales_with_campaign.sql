with sales as (
    select * from {{ ref('int_sales_enriched') }}
),

mapping as (
    select * from {{ ref('stg_campaign_sku_mapping') }}
),

campaigns as (
    select * from {{ ref('stg_dim_campaign') }}
)

select
    s.*,
    m.campaign_id,
    c.campaign_name,
    c.campaign_type,
    c.start_date      as campaign_start_date,
    c.end_date        as campaign_end_date,
    m.discount_pct    as campaign_discount_pct,
    case
        when m.campaign_id is not null
        and s.date between c.start_date and c.end_date
        then true
        else false
    end               as is_campaign_sku

from sales s
left join mapping m
    on s.sku = m.sku
left join campaigns c
    on m.campaign_id = c.campaign_id
with campaign_sales as (
    select * from {{ ref('int_sales_with_campaign') }}
),

campaigns as (
    select * from {{ ref('stg_dim_campaign') }}
)

select
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,
    c.start_date                                        as campaign_start_date,
    c.end_date                                          as campaign_end_date,

    -- Volume
    count(distinct s.transaction_id)                    as transactions,
    sum(s.quantity)                                     as units_sold,

    -- Revenue
    sum(s.gross_revenue_eur)                            as gross_revenue_eur,
    sum(s.net_revenue_eur)                              as net_revenue_eur,
    sum(s.discount_amount_eur)                          as total_discount_eur,

    -- Margin
    sum(s.gross_margin_eur)                             as total_margin_eur,
    sum(s.gross_margin_eur)
        / nullif(sum(s.net_revenue_eur), 0)             as margin_pct,

    -- Promo depth
    avg(s.discount_pct)                                 as avg_discount_pct,

    -- Basket
    sum(s.net_revenue_eur)
        / nullif(count(distinct s.transaction_id), 0)   as avg_basket_eur,

    -- SKUs and stores reached
    count(distinct s.sku)                               as distinct_skus,
    count(distinct s.store_id)                          as distinct_stores

from campaigns c
left join campaign_sales s
    on c.campaign_id = s.campaign_id
    and s.date between c.start_date and c.end_date

group by
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,
    c.start_date,
    c.end_date
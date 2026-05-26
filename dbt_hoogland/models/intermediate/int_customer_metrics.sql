with customers as (
    select * from {{ ref('stg_dim_customer') }}
),

sales as (
    select * from {{ ref('stg_fact_sales') }}
    where customer_id is not null
    and customer_id != ''
)

select
    c.customer_id,
    c.signup_date,
    c.segment,
    c.home_city,
    c.region,
    c.gender,
    c.age_band,
    c.member_tier,
    c.email_subscribed,

    -- Transaction metrics
    min(s.date)                                    as first_purchase_date,
    max(s.date)                                    as last_purchase_date,
    count(distinct s.transaction_id)               as total_transactions,
    count(s.line_id)                               as total_line_items,
    sum(s.net_revenue_eur)                         as total_net_revenue_eur,
    sum(s.gross_revenue_eur)                       as total_gross_revenue_eur,
    sum(s.discount_amount_eur)                     as total_discount_eur,
    sum(s.quantity)                                as total_units,
    avg(s.net_revenue_eur)                         as avg_line_value_eur,
    sum(s.net_revenue_eur)
        / nullif(count(distinct s.transaction_id), 0) as avg_basket_eur

from customers c
left join sales s on c.customer_id = s.customer_id

group by
    c.customer_id,
    c.signup_date,
    c.segment,
    c.home_city,
    c.region,
    c.gender,
    c.age_band,
    c.member_tier,
    c.email_subscribed
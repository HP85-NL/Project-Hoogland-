with customers as (
    select * from {{ ref('int_customer_metrics') }}
)

select
    customer_id,
    signup_date,
    segment,
    home_city,
    region,
    gender,
    age_band,
    member_tier,
    email_subscribed,

    -- Transaction history
    first_purchase_date,
    last_purchase_date,
    total_transactions,
    total_line_items,
    total_units,
    total_net_revenue_eur,
    total_gross_revenue_eur,
    total_discount_eur,
    avg_basket_eur,

    -- Tenure in days
    datediff('day', signup_date, last_purchase_date)    as tenure_days,

    -- Recency in days (from end of dataset)
    datediff('day', last_purchase_date, date '2025-12-31') as recency_days,

    -- CLV proxy (total net revenue as simple CLV)
    total_net_revenue_eur                               as clv_eur,

    -- RFM scoring
    case
        when datediff('day', last_purchase_date, date '2025-12-31') <= 30  then 5
        when datediff('day', last_purchase_date, date '2025-12-31') <= 90  then 4
        when datediff('day', last_purchase_date, date '2025-12-31') <= 180 then 3
        when datediff('day', last_purchase_date, date '2025-12-31') <= 365 then 2
        else 1
    end                                                 as recency_score,

    case
        when total_transactions >= 10 then 5
        when total_transactions >= 6  then 4
        when total_transactions >= 3  then 3
        when total_transactions >= 2  then 2
        else 1
    end                                                 as frequency_score,

    case
        when total_net_revenue_eur >= 1000 then 5
        when total_net_revenue_eur >= 500  then 4
        when total_net_revenue_eur >= 250  then 3
        when total_net_revenue_eur >= 100  then 2
        else 1
    end                                                 as monetary_score

from customers
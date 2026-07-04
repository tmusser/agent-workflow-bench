from __future__ import annotations

import pandas as pd


def product_order_denominators(orders: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        orders.groupby("product", sort=True)["order_id"]
        .nunique()
        .reset_index(name="total_orders")
    )
    grouped["total_orders"] = grouped["total_orders"].astype(int)
    return grouped


def calculate_product_refund_rates(
    orders: pd.DataFrame,
    refund_events: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate order-based refund rates by product."""
    denominators = product_order_denominators(orders)

    refunds_with_product = refund_events.merge(
        orders[["order_id", "product"]],
        on="order_id",
        how="left",
    )

    # BUG: refund rate is order-based, but this counts refund events.
    numerators = (
        refunds_with_product.groupby("product", sort=True)["refund_id"]
        .count()
        .reset_index(name="refunded_orders")
    )

    result = denominators.merge(numerators, on="product", how="left")
    result["refunded_orders"] = result["refunded_orders"].fillna(0).astype(int)
    result["refund_rate"] = result["refunded_orders"] / result["total_orders"]
    return result[["product", "total_orders", "refunded_orders", "refund_rate"]]

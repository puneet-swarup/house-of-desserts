"""Tests for the Today page — dispatch list and production aggregation."""

from datetime import datetime, timedelta
from decimal import Decimal

from app.models import OrderStatus
from app.services.order_service import create_order, update_status
from app.services.today_service import dispatch_today, production_this_week
from app.utils.time import business_today_bounds_utc


def _iso_local(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def _mk_order(db, customer, product, qty, fulfillment_dt, advance=0):
    return create_order(
        db,
        {
            "customer_id": customer.id,
            "items": [{"product_id": product.id, "quantity": qty}],
            "fulfillment_date": _iso_local(fulfillment_dt),
            "advance_paid": advance,
        },
    )


def test_dispatch_includes_today_orders(db, customer, product):
    today_start, _ = business_today_bounds_utc()
    today_noon = today_start + timedelta(hours=6)  # roughly noon local

    _mk_order(db, customer, product, 1, today_noon)

    results = dispatch_today(db)
    assert len(results) == 1
    assert results[0].customer.id == customer.id


def test_dispatch_excludes_future_and_cancelled(db, customer, product):
    today_start, _ = business_today_bounds_utc()
    today_noon = today_start + timedelta(hours=6)
    tomorrow_noon = today_noon + timedelta(days=1)

    o_today = _mk_order(db, customer, product, 1, today_noon)
    _mk_order(db, customer, product, 1, tomorrow_noon)

    # Cancel the today order
    update_status(db, o_today.id, "CANCELLED")

    results = dispatch_today(db)
    assert len(results) == 0


def test_production_buckets_by_date(db, customer, product):
    today_start, _ = business_today_bounds_utc()
    today_noon = today_start + timedelta(hours=6)
    tomorrow_noon = today_noon + timedelta(days=1)
    three_days = today_noon + timedelta(days=3)

    _mk_order(db, customer, product, 2, today_noon)
    _mk_order(db, customer, product, 3, tomorrow_noon)
    _mk_order(db, customer, product, 5, three_days)

    prod = production_this_week(db)

    assert len(prod["urgent"]) == 1
    assert prod["urgent"][0]["qty"] == 2

    assert len(prod["tomorrow"]) == 1
    assert prod["tomorrow"][0]["qty"] == 3

    assert len(prod["later"]) == 1
    assert prod["later"][0]["qty"] == 5

    assert prod["total_units"] == 10


def test_production_aggregates_same_sku(db, customer, product):
    today_start, _ = business_today_bounds_utc()
    today_noon = today_start + timedelta(hours=6)

    _mk_order(db, customer, product, 2, today_noon)
    _mk_order(db, customer, product, 3, today_noon)

    prod = production_this_week(db)
    assert len(prod["urgent"]) == 1
    assert prod["urgent"][0]["qty"] == 5
    assert prod["urgent"][0]["order_count"] == 2


def test_production_excludes_ready_orders(db, customer, product):
    today_start, _ = business_today_bounds_utc()
    today_noon = today_start + timedelta(hours=6)

    o = _mk_order(db, customer, product, 1, today_noon)
    # Move through the state machine to READY
    update_status(db, o.id, "IN_PROGRESS")
    update_status(db, o.id, "READY")

    prod = production_this_week(db)
    assert prod["total_units"] == 0


def test_production_respects_7_day_horizon(db, customer, product):
    today_start, _ = business_today_bounds_utc()
    far_future = today_start + timedelta(days=30)

    _mk_order(db, customer, product, 1, far_future)

    prod = production_this_week(db)
    assert prod["total_units"] == 0

"""
Playwright UI test fixtures.

Architecture:
- The app server runs in a SUBPROCESS with its own env. This is
  deliberate: importing the app in-process would fight with the
  root tests/conftest.py over sys.modules and the DB engine.
- The UI test DB is a real SQLite file (data/test_ui.db), wiped once
  per session, seeded by direct SQLAlchemy connection.
- Tests navigate explicitly: page.goto(live_server + "/path").
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

TEST_PORT = 8765
TEST_DB = Path("data/test_ui.db").resolve()
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def _wait_for_port(host: str, port: int, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(host, port):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Server did not open port {port} within {timeout}s")


# ---------------------------------------------------------------
# Live server (session scope, subprocess)
# ---------------------------------------------------------------

@pytest.fixture(scope="session")
def live_server():
    # Wipe any previous test DB
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(TEST_DB) + suffix)
        if p.exists():
            p.unlink()

    TEST_DB.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DB_URL"] = f"sqlite:///{TEST_DB}"
    env["SECRET_KEY"] = "ui-test-secret"
    env["DEBUG"] = "false"
    env["BUSINESS_TIMEZONE"] = "Asia/Kolkata"

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1",
            "--port", str(TEST_PORT),
            "--log-level", "warning",
            "--no-access-log",
        ],
        env=env,
        cwd=str(Path.cwd()),
    )

    try:
        _wait_for_port("127.0.0.1", TEST_PORT, timeout=25)
    except RuntimeError:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise

    yield BASE_URL

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)

    # Windows can hold file handles briefly after process exit.
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(TEST_DB) + suffix)
        for _ in range(10):
            try:
                if p.exists():
                    p.unlink()
                break
            except PermissionError:
                time.sleep(0.3)


# ---------------------------------------------------------------
# Seeded data (function scope)
# ---------------------------------------------------------------

@pytest.fixture()
def seeded(live_server):
    """
    Wipe domain tables and insert one customer + one product.
    Returns a dict with IDs and names so tests can reference them.
    Uses a fresh engine — never touches the app's module-level engine.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Import models purely to get Base.metadata populated.
    # The engine inside app.database is irrelevant here — we make our own.
    from app.models import (  # noqa: F401
        Address, Customer, Invoice, Order, OrderItem, Payment, Product,
    )
    from app.database import Base

    engine = create_engine(f"sqlite:///{TEST_DB}")
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # FK-safe wipe order
        for model in (Invoice, Payment, OrderItem, Order, Address, Customer, Product):
            db.query(model).delete()
        db.commit()

        suffix = uuid.uuid4().hex[:6]

        c = Customer(
            name=f"UI Customer {suffix}",
            phone=f"+91 90000 {suffix}",
            email=None,
            is_active=True,
        )
        db.add(c)
        db.commit()
        db.refresh(c)

        p = Product(
            sku=f"UI-CAKE-{suffix}",
            name=f"UI Test Cake {suffix}",
            category="Cake",
            base_price=350,
            gst_rate=5,
            prep_time_hours=4,
            is_active=True,
        )
        db.add(p)
        db.commit()
        db.refresh(p)

        yield {
            "customer_id": c.id,
            "customer_name": c.name,
            "customer_phone": c.phone,
            "product_id": p.id,
            "product_name": p.name,
            "product_sku": p.sku,
            "fulfillment": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT12:00"),
        }
    finally:
        db.close()
        engine.dispose()


# ---------------------------------------------------------------
# Convenience: page already navigated to /
# ---------------------------------------------------------------

@pytest.fixture()
def app_page(browser, live_server):
    """A fresh page pointed at the app root."""
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(10000)
    page.goto(live_server + "/")
    yield page
    context.close()
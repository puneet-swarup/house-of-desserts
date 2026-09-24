"""Fix the filter_by misuse in test_customers.py introduced by cleanup_ruff."""

from pathlib import Path

p = Path("tests/test_customers.py")
text = p.read_text(encoding="utf-8")

old = """    active = db_session.query(Customer).filter_by(
        Customer.phone == "+91 55555 66666", Customer.is_active.is_(True)
    ).count()"""

new = """    active = db_session.query(Customer).filter(
        Customer.phone == "+91 55555 66666",
        Customer.is_active.is_(True),
    ).count()"""

if old in text:
    p.write_text(text.replace(old, new), encoding="utf-8")
    print("Fixed.")
else:
    print("Exact pattern not found. Showing context around the issue:")
    idx = text.find("Customer.is_active.is_(True)")
    if idx >= 0:
        print(text[max(0, idx - 400):idx + 200])
    else:
        print("No reference to Customer.is_active.is_(True) — already fixed?")
"""Seed the operational tables the assistant's tools read.

Run once, after `shopstream ingest`:
    uv run python scripts/seed_orders.py

Dates are computed relative to the day you run it, so the test cases stay
meaningful instead of ageing out. The script prints the dates it used --
write your golden questions against those.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from shopstream.config import load_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id     TEXT PRIMARY KEY,
    customer     TEXT NOT NULL,
    email        TEXT NOT NULL,
    sku          TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity     INTEGER NOT NULL,
    total_eur    REAL NOT NULL,
    status       TEXT NOT NULL,
    ordered_at   TEXT NOT NULL,
    delivered_at TEXT
);

CREATE TABLE IF NOT EXISTS refund_drafts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     TEXT NOT NULL,
    amount_eur   REAL NOT NULL,
    reason       TEXT NOT NULL,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
"""

TODAY = date.today()


def ago(days: int | None) -> str | None:
    """An ISO date `days` before today, or None for 'not yet'."""
    return None if days is None else (TODAY - timedelta(days=days)).isoformat()


# order_id, customer, email, sku, product, qty, total, status, ordered_days_ago, delivered_days_ago
ROWS = [
    # --- the five shaped to make policy questions interesting --------------
    ("1042", "Mila Jovanovic", "mila.j@example.com", "SKU-4417",
     "Aurora Headphones", 1, 149.00, "delivered", 16, 12),
    ("1043", "Petar Ilic", "p.ilic@example.com", "SKU-4418",
     "Aurora Headphones Pro", 1, 229.00, "delivered", 99, 95),
    ("1044", "Ana Kovac", "ana.k@example.com", "SKU-2201",
     "Pulse Earbuds", 1, 89.00, "delivered", 12, 8),
    ("1045", "Nikola Rasic", "n.rasic@example.com", "SKU-3310",
     "Nimbus Bluetooth Speaker", 1, 119.00, "shipped", 3, None),
    ("1046", "Jelena Maric", "j.maric@example.com", "SKU-7040",
     "Cobalt Mechanical Keyboard", 1, 139.00, "delivered", 34, 30),
    # --- ordinary rows, so lookups are not trivially memorable -------------
    ("1047", "Stefan Pavlovic", "stefan.p@example.com", "SKU-8815",
     "Drift Wireless Mouse", 2, 98.00, "delivered", 41, 37),
    ("1048", "Marija Simic", "m.simic@example.com", "SKU-6120",
     "Lumen Desk Lamp", 1, 69.00, "delivered", 22, 18),
    ("1049", "Luka Djordjevic", "luka.d@example.com", "SKU-5502",
     "Vertex 7-in-1 USB-C Hub", 1, 59.00, "delivered", 9, 5),
    ("1050", "Teodora Nikolic", "teo.n@example.com", "SKU-4417",
     "Aurora Headphones", 1, 149.00, "returned", 73, 68),
    ("1051", "Vuk Stankovic", "vuk.s@example.com", "SKU-3310",
     "Nimbus Bluetooth Speaker", 2, 238.00, "delivered", 55, 50),
    ("1052", "Sara Lukic", "sara.l@example.com", "SKU-2201",
     "Pulse Earbuds", 1, 89.00, "delivered", 28, 24),
    ("1053", "Filip Tomic", "filip.t@example.com", "SKU-7040",
     "Cobalt Mechanical Keyboard", 1, 139.00, "placed", 1, None),
    ("1054", "Dunja Ristic", "dunja.r@example.com", "SKU-6120",
     "Lumen Desk Lamp", 3, 207.00, "delivered", 61, 56),
    ("1055", "Bogdan Savic", "b.savic@example.com", "SKU-4418",
     "Aurora Headphones Pro", 1, 229.00, "delivered", 19, 14),
    ("1056", "Iva Mitrovic", "iva.m@example.com", "SKU-8815",
     "Drift Wireless Mouse", 1, 49.00, "shipped", 2, None),
    ("1057", "Aleksa Popovic", "aleksa.p@example.com", "SKU-5502",
     "Vertex 7-in-1 USB-C Hub", 2, 118.00, "delivered", 88, 83),
    ("1058", "Milica Djukic", "milica.d@example.com", "SKU-4417",
     "Aurora Headphones", 1, 149.00, "delivered", 45, 40),
    ("1059", "Relja Babic", "relja.b@example.com", "SKU-3310",
     "Nimbus Bluetooth Speaker", 1, 119.00, "returned", 110, 104),
    ("1060", "Katarina Vasic", "k.vasic@example.com", "SKU-2201",
     "Pulse Earbuds", 2, 178.00, "delivered", 7, 3),
    ("1061", "Ognjen Maksimovic", "ognjen.m@example.com", "SKU-6120",
     "Lumen Desk Lamp", 1, 69.00, "placed", 0, None),
]


def main() -> None:
    settings = load_settings()
    db = sqlite3.connect(settings.db_path)
    db.executescript(SCHEMA)

    with db:
        db.execute("DELETE FROM orders")                 # idempotent re-seed
        db.executemany(
            "INSERT INTO orders (order_id, customer, email, sku, product_name,"
            " quantity, total_eur, status, ordered_at, delivered_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(oid, cust, mail, sku, prod, qty, total, status,
              ago(od), ago(dd))
             for oid, cust, mail, sku, prod, qty, total, status, od, dd in ROWS],
        )

    n = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    print(f"seeded {n} orders into {settings.db_path}")
    print(f"today is {TODAY.isoformat()}; the 30-day return window opens on "
          f"{ago(30)}\n")

    print("the cases worth writing golden questions against:")
    for oid in ("1042", "1043", "1044", "1045", "1046"):
        r = db.execute(
            "SELECT order_id, product_name, status, delivered_at"
            " FROM orders WHERE order_id = ?", (oid,)).fetchone()
        print(f"  #{r[0]}  {r[1]:<28} {r[2]:<10} delivered {r[3] or '-'}")


if __name__ == "__main__":
    main()
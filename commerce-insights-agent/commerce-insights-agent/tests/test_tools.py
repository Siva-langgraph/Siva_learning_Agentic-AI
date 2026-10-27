import sqlite3
from app.db import Database, set_db_for_tests
from app.tools import run_tool

def test_tool_rejects_unknown_tool():
    assert run_tool("execute_sql", {"sql":"DROP TABLE orders"}) == {"error":"Tool not allowed"}
def test_tool_argument_validation():
    assert "error" in run_tool("search_products", {"keyword":"x"*61})
def test_sqlite_database_queries(tmp_path):
    dbpath = tmp_path / "test.db"
    with sqlite3.connect(dbpath) as c:
        c.executescript("CREATE TABLE products(id INTEGER PRIMARY KEY,sku TEXT,name TEXT,category TEXT,unit_price REAL); CREATE TABLE orders(id INTEGER PRIMARY KEY,order_date TEXT,status TEXT,customer_region TEXT,total_amount REAL); CREATE TABLE order_items(id INTEGER PRIMARY KEY,order_id INTEGER,product_id INTEGER,quantity INTEGER,unit_price REAL); INSERT INTO orders VALUES(1,'2026-01-01','paid','South',50.0);")
    set_db_for_tests(Database(f"sqlite:///{dbpath}"))
    try: assert run_tool("sales_summary", {"group_by":"none"})["rows"][0]["order_count"] == 1
    finally: set_db_for_tests(None)

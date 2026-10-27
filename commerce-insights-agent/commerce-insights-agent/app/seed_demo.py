"""Create/seed a local SQLite demo database. Refuses to seed PostgreSQL."""
import sqlite3
from pathlib import Path
from .config import settings
def main():
    if not settings.database_url.startswith("sqlite:"): raise SystemExit("Refusing to seed a non-SQLite database")
    raw = settings.database_url.removeprefix("sqlite:///")
    path = Path(raw)
    if str(path) != ":memory:": path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as c:
        c.executescript("CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,sku TEXT UNIQUE NOT NULL,name TEXT NOT NULL,category TEXT NOT NULL,unit_price REAL NOT NULL CHECK(unit_price>=0)); CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY,order_date TEXT NOT NULL,status TEXT NOT NULL,customer_region TEXT NOT NULL,total_amount REAL NOT NULL CHECK(total_amount>=0)); CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES orders(id),product_id INTEGER NOT NULL REFERENCES products(id),quantity INTEGER NOT NULL CHECK(quantity>0),unit_price REAL NOT NULL CHECK(unit_price>=0));")
        c.executemany("INSERT OR IGNORE INTO products(sku,name,category,unit_price) VALUES(?,?,?,?)", [("AUD-100","Wireless Noise-Cancelling Headset","audio",89.99),("ACC-200","Mechanical Keyboard","accessories",74.00),("ACC-300","Wireless Mouse","accessories",24.99)])
        if c.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
            c.executemany("INSERT INTO orders(order_date,status,customer_region,total_amount) VALUES(date('now'),?,?,?)", [("paid","South",114.98),("shipped","West",89.99),("pending","North",74.00)])
            c.executemany("INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES(?,?,?,?)", [(1,1,1,89.99),(1,3,1,24.99),(2,1,1,89.99),(3,2,1,74.00)])
    print(f"Demo database ready: {path}")
if __name__ == "__main__": main()

from __future__ import annotations
from typing import Any
from .db import get_db
TOOL_SCHEMAS = [
 {"type":"function","function":{"name":"sales_summary","description":"Summarize order count and sales total, optionally by status or region.","strict":True,"parameters":{"type":"object","properties":{"group_by":{"type":"string","enum":["none","status","region"]}},"required":["group_by"],"additionalProperties":False}}},
 {"type":"function","function":{"name":"top_products","description":"List products ranked by units sold and sales value.","strict":True,"parameters":{"type":"object","properties":{"limit":{"type":"integer","minimum":1,"maximum":10}},"required":["limit"],"additionalProperties":False}}},
 {"type":"function","function":{"name":"orders_by_status","description":"Count orders by current status.","strict":True,"parameters":{"type":"object","properties":{},"required":[],"additionalProperties":False}}},
 {"type":"function","function":{"name":"search_products","description":"Search product names/categories by a short keyword.","strict":True,"parameters":{"type":"object","properties":{"keyword":{"type":"string","minLength":1,"maxLength":60}},"required":["keyword"],"additionalProperties":False}}}
]
def run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(args, dict): return {"error":"Tool arguments must be an object"}
    db = get_db()
    if name == "sales_summary":
        group = args.get("group_by", "none")
        if group not in {"none", "status", "region"}: return {"error":"Unsupported grouping"}
        if group == "none": sql = "SELECT COUNT(*) AS order_count, COALESCE(SUM(total_amount),0) AS sales_total FROM orders"
        else: sql = f"SELECT {group} AS group_name, COUNT(*) AS order_count, COALESCE(SUM(total_amount),0) AS sales_total FROM orders GROUP BY {group} ORDER BY sales_total DESC LIMIT 100"
        return {"rows":db.rows(sql)}
    if name == "top_products":
        try: limit = max(1, min(10, int(args.get("limit", 5))))
        except (TypeError, ValueError): return {"error":"limit must be an integer"}
        sql = "SELECT p.sku, p.name, COALESCE(SUM(oi.quantity),0) AS units_sold, COALESCE(SUM(oi.quantity * oi.unit_price),0) AS sales_total FROM products p LEFT JOIN order_items oi ON oi.product_id=p.id GROUP BY p.id,p.sku,p.name ORDER BY sales_total DESC, units_sold DESC LIMIT " + str(limit)
        return {"rows":db.rows(sql)}
    if name == "orders_by_status": return {"rows":db.rows("SELECT status, COUNT(*) AS order_count FROM orders GROUP BY status ORDER BY order_count DESC LIMIT 20")}
    if name == "search_products":
        keyword = args.get("keyword")
        if not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 60: return {"error":"keyword must contain 1-60 characters"}
        if db.url.startswith("sqlite:"): sql = "SELECT sku,name,category,unit_price FROM products WHERE lower(name) LIKE lower(?) OR lower(category) LIKE lower(?) ORDER BY name LIMIT 20"
        else: sql = "SELECT sku,name,category,unit_price FROM products WHERE name ILIKE %s OR category ILIKE %s ORDER BY name LIMIT 20"
        pattern = "%" + keyword.strip() + "%"
        return {"rows":db.rows(sql,(pattern,pattern))}
    return {"error":"Tool not allowed"}

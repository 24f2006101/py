from fastapi import FastAPI, Request
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import re

app = FastAPI()

with open("data.json", "r", encoding="utf-8") as f:
    saved = json.load(f)

ORDERS = saved["orders"]
RATES = saved["rates"]
IST = ZoneInfo("Asia/Kolkata")

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

def parse_month(question):
    q = question.lower()

    for name, number in MONTHS.items():
        if name in q:
            year_match = re.search(r"\b(20\d{2})\b", q)
            if year_match:
                return int(year_match.group(1)), number

    return None, None

def get_date(order):
    # Change "created_at" if your order uses another date field
    return datetime.fromisoformat(order["created_at"]).astimezone(IST)

def to_usd(order):
    amount = float(order["amount"])  # change if your money field differs
    currency = order["currency"]

    if currency == "USD":
        return amount

    return amount * RATES[currency]

@app.post("/")
async def answer(request: Request):
    body = await request.json()
    question = body.get("question", "")
    q = question.lower()

    year, month = parse_month(q)
    rows = ORDERS

    # Filter by month
    if year and month:
        rows = [
            r for r in rows
            if get_date(r).year == year and get_date(r).month == month
        ]

    # Filter by region
    for region in ["north", "south", "east", "west"]:
        if region in q:
            rows = [
                r for r in rows
                if r.get("region", "").lower() == region
            ]
            break

    # Filter by product name.
    # This finds a capitalized product name in the original question.
       # Build the list of real product names from your data
    products = sorted({
        r.get("product", "")
        for r in ORDERS
        if r.get("product")
    })

    # Filter by a real product name only
    matched_product = None
    for product in products:
        if product.lower() in q:
            matched_product = product
            break

    if matched_product:
        rows = [
            r for r in rows
            if r.get("product") == matched_product
        ]
    # Refund questions
    if "refund" in q:
        rows = [
            r for r in rows
            if r.get("status", "").lower() == "refunded"
        ]
        total = sum(to_usd(r) for r in rows)
        return {"answer": round(total, 2)}

    # Paid orders only for customer/revenue questions
    rows = [r for r in rows if r.get("status") == "paid"]

    # Distinct customer count
    if "distinct customer" in q or "how many customers" in q or "unique customers" in q:
        customers = set()

        for r in rows:
            customer = r.get("customer_id") or r.get("customer") or r.get("customer_name")
            if customer:
                customers.add(customer)

        return {"answer": len(customers)}

    # Average order value
    if "average" in q or "on average" in q or "mean" in q:
        if not rows:
            return {"answer": 0}
        total = sum(to_usd(r) for r in rows)
        return {"answer": round(total / len(rows), 2)}

    # Number of orders
    if "how many orders" in q or "number of orders" in q:
        return {"answer": len(rows)}

    # Default: total revenue in USD
    total = sum(to_usd(r) for r in rows)
    return {"answer": round(total, 2)}

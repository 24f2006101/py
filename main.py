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
    return datetime.fromisoformat(order["created_at"]).astimezone(IST)


def to_usd(order):
    amount = float(order["amount"])
    currency = order["currency"]

    if currency == "USD":
        return amount

    return amount * RATES[currency]


def revenue_by_product(rows):
    totals = {}

    for order in rows:
        product = order.get("product")
        if not product:
            continue

        totals[product] = totals.get(product, 0) + to_usd(order)

    return totals


@app.post("/")
async def answer(request: Request):
    body = await request.json()
    question = body.get("question", "")
    q = question.lower()

    year, month = parse_month(q)
    rows = ORDERS

    # 1. Month filter
    if year and month:
        rows = [
            order for order in rows
            if get_date(order).year == year
            and get_date(order).month == month
        ]

    # 2. Region filter
    for region in ["north", "south", "east", "west"]:
        if region in q:
            rows = [
                order for order in rows
                if order.get("region", "").lower() == region
            ]
            break

    # 3. Product filter: use only real product names from the data
    products = sorted({
        order.get("product", "")
        for order in ORDERS
        if order.get("product")
    })

    matched_product = None

    for product in products:
        if product.lower() in q:
            matched_product = product
            break

    if matched_product:
        rows = [
            order for order in rows
            if order.get("product") == matched_product
        ]

       # 4. Refund questions
    if "refund" in q:
        refund_rows = [
            order for order in rows
            if order.get("status", "").lower() == "refunded"
        ]

        # Count questions
        count_phrases = [
            "how many orders",
            "number of orders",
            "how many refunds",
            "number of refunds",
            "how many were refunded",
            "how many orders from",
        ]

        if any(phrase in q for phrase in count_phrases):
            return {"answer": len(refund_rows)}

        # Otherwise, assume refund revenue in USD
        total = sum(to_usd(order) for order in refund_rows)
        return {"answer": round(total, 2)}

    # 5. Paid orders only for all remaining questions
    rows = [
        order for order in rows
        if order.get("status") == "paid"
    ]

    # 6. Top product by revenue
    top_product_phrases = [
        "which product earned the most",
        "which product had the highest revenue",
        "which product generated the most revenue",
        "top-selling product",
        "top selling product",
        "best-selling product",
        "best selling product",
        "highest revenue product",
        "most revenue product",
    ]

    if any(phrase in q for phrase in top_product_phrases):
        totals = revenue_by_product(rows)

        if not totals:
            return {"answer": ""}

        top_product = max(totals, key=totals.get)
        return {"answer": top_product}

        # 7. Customer-count questions
    customer_count_phrases = [
        "how many different customers",
        "how many distinct customers",
        "how many unique customers",
        "how many customers",
        "different customers",
        "distinct customers",
        "unique customers",
        "number of customers",
    ]

    if any(phrase in q for phrase in customer_count_phrases):
        customers = set()

        for order in rows:
            customer = (
                order.get("customer_id")
                or order.get("customer")
                or order.get("customer_name")
            )

            if customer:
                customers.add(customer)

        return {"answer": len(customers)}
    # 8. Average paid order value
    if "average" in q or "on average" in q or "mean" in q:
        if not rows:
            return {"answer": 0}

        total = sum(to_usd(order) for order in rows)
        return {"answer": round(total / len(rows), 2)}

    # 9. Number of orders
    if "how many orders" in q or "number of orders" in q:
        return {"answer": len(rows)}

    # 10. Default: total revenue in USD
    total = sum(to_usd(order) for order in rows)
    return {"answer": round(total, 2)}

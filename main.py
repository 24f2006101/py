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

    # Refund or revenue
     # Refund or revenue
    if "refund" in q:
        rows = [
            r for r in rows
            if r.get("status", "").lower() == "refunded"
        ]
        total = sum(to_usd(r) for r in rows)
        return {"answer": round(total, 2)}

    # Keep only paid orders for revenue-type questions
    rows = [r for r in rows if r.get("status") == "paid"]

    total = sum(to_usd(r) for r in rows)
    count = len(rows)

    # Average question
    if "average" in q or "on average" in q or "mean" in q:
        if count == 0:
            return {"answer": 0}
        return {"answer": round(total / count, 2)}

    # Normal total revenue question
    return {"answer": round(total, 2)}

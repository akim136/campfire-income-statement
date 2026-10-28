"""One FastAPI server; the accounting engine is shared by JSON and HTML."""

from datetime import date
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.report import build_income_statement


PROJECT_DIR = Path(__file__).resolve().parent.parent
LEDGER = json.loads((PROJECT_DIR / "ledger.json").read_text(encoding="utf-8"))

app = FastAPI(title="Income Statement", version="0.1.0")


def validate_date_range(start: date, end: date) -> None:
    if start > end:
        # Use the same status and error shape as FastAPI's native date validation.
        raise RequestValidationError([
            {
                "type": "value_error",
                "loc": ("query", "end"),
                "msg": "Start date must be on or before the end date.",
                "input": end.isoformat(),
            }
        ])


@app.get("/income-statement")
def income_statement(start: date, end: date) -> dict:
    """Posted P&L for inclusive dates. All monetary values are integer cents."""
    validate_date_range(start, end)
    return build_income_statement(LEDGER, start, end)

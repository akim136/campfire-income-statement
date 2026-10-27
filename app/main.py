"""One FastAPI server; the accounting engine is shared by JSON and HTML."""

from datetime import date
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.report import build_income_statement


PROJECT_DIR = Path(__file__).resolve().parent.parent
LEDGER = json.loads((PROJECT_DIR / "ledger.json").read_text(encoding="utf-8"))

app = FastAPI(title="Income Statement", version="0.1.0")
app.mount("/static", StaticFiles(directory=PROJECT_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=PROJECT_DIR / "app" / "templates")
DEFAULT_START = date(2026, 1, 1)
DEFAULT_END = date(2026, 3, 31)


def format_money(amount_cents: int) -> str:
    """Format cents for display without converting through a float."""
    dollars, cents = divmod(abs(amount_cents), 100)
    formatted = f"${dollars:,}.{cents:02d}"
    return f"({formatted})" if amount_cents < 0 else formatted


def format_date(iso_date: str) -> str:
    value = date.fromisoformat(iso_date)
    return f"{value:%B} {value.day}, {value.year}"


templates.env.filters["money"] = format_money
templates.env.filters["date_label"] = format_date


def render_page(request, report=None, *, error=None, invalid_fields=(), status_code=200):
    period = report["period"] if report else {
        "start": request.query_params.get("start", DEFAULT_START.isoformat()),
        "end": request.query_params.get("end", DEFAULT_END.isoformat()),
    }
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "company": LEDGER["company"],
            "start": period["start"],
            "end": period["end"],
            "report": report,
            "error": error,
            "invalid_fields": invalid_fields,
        },
        status_code=status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    if request.url.path != "/":
        return await request_validation_exception_handler(request, exc)
    errors = exc.errors()
    invalid_fields = {error["loc"][-1] for error in errors}
    message = "Enter valid dates in YYYY-MM-DD format."
    if any(error["type"] == "value_error" for error in errors):
        message = "Start date must be on or before the end date."
        invalid_fields = {"start", "end"}
    return render_page(request, error=message, invalid_fields=invalid_fields, status_code=422)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    if request.url.path == "/":
        return render_page(
            request,
            error="The statement could not be loaded. Apply dates again to retry.",
            status_code=500,
        )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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


@app.get("/income-statement", responses={500: {"description": "Unexpected server error"}})
def income_statement(start: date, end: date) -> dict:
    """Posted P&L for inclusive dates. All monetary values are integer cents."""
    validate_date_range(start, end)
    return build_income_statement(LEDGER, start, end)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request, start: date = DEFAULT_START, end: date = DEFAULT_END):
    validate_date_range(start, end)
    report = build_income_statement(LEDGER, start, end)
    return render_page(request, report)

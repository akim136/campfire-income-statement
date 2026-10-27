"""Pure income-statement calculations. All aggregated amounts are integer cents."""

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext


REVENUE_SUBTYPES = {"operating_revenue", "contra_revenue", "other_income"}
PNL_SUBTYPES = REVENUE_SUBTYPES | {"cogs", "operating_expense"}


def to_cents(value: str) -> int:
    """Parse a nonnegative decimal string without rounding fractional cents."""
    if not isinstance(value, str):
        raise ValueError("Monetary amounts must be decimal strings.")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid monetary amount.") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Debit and credit amounts must be finite and nonnegative.")
    # Preserve every digit even if a supplied amount exceeds Decimal's default precision.
    with localcontext() as context:
        context.prec = max(28, len(amount.as_tuple().digits) + 2)
        cents = amount * 100
        if cents != cents.to_integral_value():
            raise ValueError("Monetary amounts must contain whole cents.")
        return int(cents)


def _section_rows(accounts, balances, subtypes, label, subtotal_label):
    """Build one section from already calculated account balances."""
    lines = [
        {
            "type": "line",
            "label": account["name"],
            "accountNumber": account["number"],
            "amountCents": balances[account["number"]],
        }
        for account in accounts
        if account["subtype"] in subtypes
    ]
    total = sum(line["amountCents"] for line in lines)
    return [
        {"type": "header", "label": label},
        *lines,
        {"type": "subtotal", "label": subtotal_label, "amountCents": total},
    ], total


def build_income_statement(ledger: dict, start_date: date, end_date: date) -> dict:
    """Report posted P&L activity, including both boundary dates.

    The supplied ledger uses numeric account numbers and the assignment's subtypes.
    Inactive accounts retain their history. Zero-balance accounts remain in the rows;
    hasActivity tracks nonzero postings, including postings that cancel each other.
    No input is modified and no files, clocks, or external services are consulted.
    """
    if start_date > end_date:
        raise ValueError("Start date must be on or before the end date.")

    accounts_by_number = {account["number"]: account for account in ledger["accounts"]}
    accounts = sorted(
        (account for account in ledger["accounts"] if account["type"] in {"revenue", "expense"}),
        key=lambda account: int(account["number"]),
    )
    if any(account["subtype"] not in PNL_SUBTYPES for account in accounts):
        raise ValueError("Unsupported income-statement account subtype.")
    balances = {account["number"]: 0 for account in accounts}
    has_activity = False

    for entry in ledger["journal_entries"]:
        if entry["status"] != "posted":
            continue
        if not start_date <= date.fromisoformat(entry["date"]) <= end_date:
            continue
        for line in entry["lines"]:
            account = accounts_by_number[line["account"]]
            number = account["number"]
            if number not in balances:
                continue
            debit = to_cents(line["debit"])
            credit = to_cents(line["credit"])
            if debit or credit:
                has_activity = True
            if account["subtype"] in REVENUE_SUBTYPES:
                balances[number] += credit - debit
            else:
                balances[number] += debit - credit

    revenue_rows, net_revenue = _section_rows(
        accounts, balances, {"operating_revenue", "contra_revenue"}, "Revenue", "Net Revenue"
    )
    cogs_rows, cogs = _section_rows(
        accounts, balances, {"cogs"}, "Cost of Goods Sold", "Total COGS"
    )
    expense_rows, operating_expenses = _section_rows(
        accounts, balances, {"operating_expense"}, "Operating Expenses", "Total Operating Expenses"
    )
    other_rows, other_income = _section_rows(
        accounts, balances, {"other_income"}, "Other Income", "Total Other Income"
    )
    gross_profit = net_revenue - cogs
    operating_income = gross_profit - operating_expenses
    net_income = operating_income + other_income

    return {
        "company": ledger["company"],
        "currency": ledger["currency"],
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "hasActivity": has_activity,
        "rows": [
            *revenue_rows,
            *cogs_rows,
            {"type": "summary", "label": "Gross Profit", "amountCents": gross_profit},
            *expense_rows,
            {"type": "summary", "label": "Operating Income", "amountCents": operating_income},
            *other_rows,
            {"type": "net", "label": "Net Income", "amountCents": net_income},
        ],
        "totals": {
            "netRevenueCents": net_revenue,
            "cogsCents": cogs,
            "grossProfitCents": gross_profit,
            "operatingExpensesCents": operating_expenses,
            "operatingIncomeCents": operating_income,
            "otherIncomeCents": other_income,
            "netIncomeCents": net_income,
        },
    }

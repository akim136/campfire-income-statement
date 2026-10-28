from copy import deepcopy
from datetime import date
from decimal import Decimal, localcontext

import pytest

from app.report import build_income_statement, to_cents


def report_for(ledger, start="2026-01-01", end="2026-03-31"):
    return build_income_statement(ledger, date.fromisoformat(start), date.fromisoformat(end))


def account_amounts(report):
    return {
        row["accountNumber"]: row["amountCents"]
        for row in report["rows"]
        if row["type"] == "line"
    }


def test_supplied_ledger_is_complete_and_balanced(ledger):
    assert len(ledger["accounts"]) == 15
    assert len(ledger["journal_entries"]) == 25
    assert len({account["number"] for account in ledger["accounts"]}) == 15
    assert len({entry["id"] for entry in ledger["journal_entries"]}) == 25
    for entry in ledger["journal_entries"]:
        assert sum(Decimal(line["debit"]) for line in entry["lines"]) == sum(
            Decimal(line["credit"]) for line in entry["lines"]
        )


def test_q1_reconciles_every_account_and_subtotal(ledger):
    report = report_for(ledger)
    assert report["company"] == "Northwind Coffee Roasters"
    assert report["currency"] == "USD"
    assert report["period"] == {"start": "2026-01-01", "end": "2026-03-31"}
    assert report["hasActivity"] is True
    assert account_amounts(report) == {
        "4000": 3565075,
        "4100": 300000,
        "4900": -80025,
        "5000": 1427275,
        "6000": 5550000,
        "6100": 900000,
        "6200": 109997,
        "6300": 250010,
        "7000": 4218,
    }
    assert report["totals"] == {
        "netRevenueCents": 3785050,
        "cogsCents": 1427275,
        "grossProfitCents": 2357775,
        "operatingExpensesCents": 6810007,
        "operatingIncomeCents": -4452232,
        "otherIncomeCents": 4218,
        "netIncomeCents": -4448014,
    }
    assert [row["amountCents"] for row in report["rows"] if row["type"] != "line" and "amountCents" in row] == [
        3785050, 1427275, 2357775, 6810007, -4452232, 4218, -4448014
    ]


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ("2026-01-01", "2026-01-31", -2152965),
        ("2026-02-01", "2026-02-28", -1323025),
        ("2026-03-01", "2026-03-31", -972024),
        ("2026-01-01", "2026-01-01", -900000),
        ("2026-02-03", "2026-02-03", 492000),
        ("2026-03-31", "2026-03-31", -1745782),
        ("2026-04-01", "2026-04-01", 910000),
        ("2026-04-02", "2026-04-04", 0),
        ("2025-12-15", "2025-12-15", 500000),
    ],
)
def test_months_and_inclusive_single_day_boundaries(ledger, start, end, expected):
    assert report_for(ledger, start, end)["totals"]["netIncomeCents"] == expected


def test_months_add_up_to_q1(ledger):
    monthly_net = sum(
        report_for(ledger, start, end)["totals"]["netIncomeCents"]
        for start, end in [
            ("2026-01-01", "2026-01-31"),
            ("2026-02-01", "2026-02-28"),
            ("2026-03-01", "2026-03-31"),
        ]
    )
    assert monthly_net == report_for(ledger)["totals"]["netIncomeCents"]


@pytest.mark.parametrize("status", ["draft", "void"])
def test_unposted_entries_have_no_effect(ledger, status):
    ledger["journal_entries"] = [
        entry for entry in ledger["journal_entries"] if entry["status"] == status
    ]
    report = report_for(ledger)
    assert report["hasActivity"] is False
    assert all(value == 0 for value in report["totals"].values())


def test_contra_revenue_reduces_revenue_and_multiline_entry_is_complete(ledger):
    report = report_for(ledger, "2026-03-02", "2026-03-02")
    amounts = account_amounts(report)
    assert amounts["4000"] == 1500000
    assert amounts["4900"] == -15000
    assert amounts["5000"] == 601245
    assert report["totals"]["netRevenueCents"] == 1485000
    assert report["totals"]["netIncomeCents"] == 883755


def test_inactive_account_keeps_historical_expense(ledger):
    assert next(account for account in ledger["accounts"] if account["number"] == "6300")["is_active"] is False
    assert account_amounts(report_for(ledger))["6300"] == 250010


@pytest.mark.parametrize("day", ["2026-01-10", "2026-02-15"])
def test_deferred_billing_and_cash_collection_are_not_income(ledger, day):
    report = report_for(ledger, day, day)
    assert report["hasActivity"] is False
    assert all(value == 0 for value in report["totals"].values())


def test_only_recognized_subscriptions_count(ledger):
    assert account_amounts(report_for(ledger))["4100"] == 300000


def test_vendor_credit_reduces_software_expense(ledger):
    report = report_for(ledger, "2026-03-20", "2026-03-20")
    assert account_amounts(report)["6200"] == -10000
    assert report["totals"]["netIncomeCents"] == 10000
    assert account_amounts(report_for(ledger))["6200"] == 109997


def test_rent_stays_entirely_in_january(ledger):
    assert account_amounts(report_for(ledger, "2026-01-01", "2026-01-31"))["6100"] == 900000
    assert account_amounts(report_for(ledger, "2026-02-01", "2026-03-31"))["6100"] == 0


def test_empty_period_has_zero_totals_but_retains_statement_structure(ledger):
    report = report_for(ledger, "2026-04-02", "2026-04-04")
    assert report["hasActivity"] is False
    assert len(account_amounts(report)) == 9
    assert all(value == 0 for value in report["totals"].values())


def test_result_is_pure_deterministic_and_sorted_by_account_number(ledger):
    original = deepcopy(ledger)
    expected = report_for(ledger)
    assert ledger == original
    assert report_for(ledger) == expected
    ledger["accounts"].reverse()
    ledger["journal_entries"].reverse()
    for entry in ledger["journal_entries"]:
        entry["lines"].reverse()
    assert report_for(ledger) == expected
    assert list(account_amounts(expected)) == ["4000", "4100", "4900", "5000", "6000", "6100", "6200", "6300", "7000"]


def test_reversed_range_is_rejected(ledger):
    with pytest.raises(ValueError, match="Start date must be on or before"):
        report_for(ledger, "2026-04-01", "2026-01-01")


def test_synthetic_ledger_uses_exact_cents_and_postings_not_net_income_for_activity():
    # Independently specified: 10c + 20c revenue, 5c returns, and 25c expense = 0c net.
    ledger = {
        "company": "Tiny Example",
        "currency": "USD",
        "accounts": [
            {"number": "10", "name": "Sales", "type": "revenue", "subtype": "operating_revenue", "is_active": True},
            {"number": "2", "name": "Returns", "type": "revenue", "subtype": "contra_revenue", "is_active": True},
            {"number": "30", "name": "Supplies", "type": "expense", "subtype": "operating_expense", "is_active": False},
        ],
        "journal_entries": [
            {
                "id": "tiny-1", "date": "2024-02-29", "status": "posted", "memo": "Balanced cent amounts",
                "lines": [
                    {"account": "10", "debit": "0.00", "credit": "0.10"},
                    {"account": "10", "debit": "0.00", "credit": "0.20"},
                    {"account": "2", "debit": "0.05", "credit": "0.00"},
                    {"account": "30", "debit": "0.25", "credit": "0.00"},
                ],
            }
        ],
    }
    report = report_for(ledger, "2024-02-29", "2024-02-29")
    assert list(account_amounts(report)) == ["2", "10", "30"]
    assert account_amounts(report) == {"2": -5, "10": 30, "30": 25}
    assert report["totals"]["netRevenueCents"] == 25
    assert report["totals"]["operatingExpensesCents"] == 25
    assert report["totals"]["netIncomeCents"] == 0
    assert report["hasActivity"] is True


@pytest.mark.parametrize("amount,expected", [("0.00", 0), ("0.10", 10), ("1199.97", 119997)])
def test_decimal_strings_convert_to_integer_cents(amount, expected):
    assert to_cents(amount) == expected
    assert type(to_cents(amount)) is int


@pytest.mark.parametrize("amount", ["0.001", "-1.00", "NaN", "Infinity", "oops", 0.1])
def test_invalid_money_is_rejected_instead_of_rounded(amount):
    with pytest.raises(ValueError):
        to_cents(amount)


def test_offsetting_postings_are_activity_even_when_every_balance_is_zero(ledger):
    sale = deepcopy(ledger["journal_entries"][1])
    reversal = deepcopy(sale)
    reversal["id"] = "test-reversal"
    for line in reversal["lines"]:
        line["debit"], line["credit"] = line["credit"], line["debit"]
    ledger["journal_entries"] = [sale, reversal]
    report = report_for(ledger)
    assert report["hasActivity"] is True
    assert all(value == 0 for value in account_amounts(report).values())
    assert all(value == 0 for value in report["totals"].values())


def test_zero_only_lines_do_not_count_as_activity(ledger):
    for entry in ledger["journal_entries"]:
        for line in entry["lines"]:
            line["debit"] = line["credit"] = "0.00"
    assert report_for(ledger)["hasActivity"] is False


def test_exact_conversion_is_independent_of_decimal_context():
    with localcontext() as context:
        context.prec = 4
        assert to_cents("1234567890123456789012345678.90") == 123456789012345678901234567890
        assert context.prec == 4
        with pytest.raises(ValueError, match="whole cents"):
            to_cents("1.0000000000000000000000000001")


def test_unsupported_pnl_subtype_is_not_silently_dropped(ledger):
    ledger["accounts"][6]["subtype"] = "unknown"
    with pytest.raises(ValueError, match="Unsupported"):
        report_for(ledger)


def test_unknown_account_reference_fails_instead_of_omitting_activity(ledger):
    ledger["journal_entries"][1]["lines"][1]["account"] = "9999"
    with pytest.raises(KeyError):
        report_for(ledger)


def test_all_entry_date_ranges_match_independent_decimal_net_calculation(ledger):
    # Net income also equals total credits minus total debits over ALL P&L accounts.
    # This independent formulation avoids the engine's section/subtotal calculations.
    pnl_accounts = {
        account["number"] for account in ledger["accounts"]
        if account["type"] in {"revenue", "expense"}
    }
    dates = sorted({entry["date"] for entry in ledger["journal_entries"]})
    for start_index, start in enumerate(dates):
        for end in dates[start_index:]:
            expected_dollars = sum(
                (
                    Decimal(line["credit"]) - Decimal(line["debit"])
                    for entry in ledger["journal_entries"]
                    if entry["status"] == "posted" and start <= entry["date"] <= end
                    for line in entry["lines"]
                    if line["account"] in pnl_accounts
                ),
                Decimal("0"),
            )
            report = report_for(ledger, start, end)
            assert report["totals"]["netIncomeCents"] == int(expected_dollars * 100), (start, end)

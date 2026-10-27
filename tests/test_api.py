from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app, format_money


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "start,end,net_income",
    [
        ("2026-01-01", "2026-03-31", -4448014),
        ("2026-02-03", "2026-02-03", 492000),
        ("2026-04-01", "2026-04-01", 910000),
    ],
)
def test_api_returns_real_income_statement(client, start, end, net_income):
    response = client.get("/income-statement", params={"start": start, "end": end})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    report = response.json()
    assert set(report) == {"company", "currency", "period", "hasActivity", "rows", "totals"}
    assert report["period"] == {"start": start, "end": end}
    assert report["hasActivity"] is True
    assert report["totals"]["netIncomeCents"] == net_income
    assert {row["type"] for row in report["rows"]} == {"header", "line", "subtotal", "summary", "net"}
    for row in report["rows"]:
        if row["type"] == "header":
            assert "amountCents" not in row
        else:
            assert type(row["amountCents"]) is int
    assert all(type(value) is int for value in report["totals"].values())


def test_api_empty_period(client):
    response = client.get("/income-statement", params={"start": "2026-04-02", "end": "2026-04-04"})
    assert response.status_code == 200
    report = response.json()
    assert report["hasActivity"] is False
    assert report["totals"]["netIncomeCents"] == 0
    assert all(row.get("amountCents", 0) == 0 for row in report["rows"])


@pytest.mark.parametrize(
    "params,field",
    [
        ({}, "start"),
        ({"start": "2026-01-01"}, "end"),
        ({"end": "2026-03-31"}, "start"),
        ({"start": "not-a-date", "end": "2026-03-31"}, "start"),
        ({"start": "2026-01-01", "end": "not-a-date"}, "end"),
        ({"start": "2026-02-30", "end": "2026-03-31"}, "start"),
        ({"start": "", "end": "2026-03-31"}, "start"),
        ({"start": "2026-01-01", "end": ""}, "end"),
        ({"start": "2026-04-01", "end": "2026-03-31"}, "end"),
    ],
)
def test_missing_invalid_and_reversed_dates_use_documented_422(client, params, field):
    response = client.get("/income-statement", params=params)
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert isinstance(errors, list)
    assert any(error["loc"] == ["query", field] for error in errors)
    assert all({"loc", "msg", "type"} <= set(error) for error in errors)
    operation = client.get("/openapi.json").json()["paths"]["/income-statement"]["get"]
    assert str(response.status_code) in operation["responses"]


def test_reversed_dates_have_clear_message(client):
    response = client.get("/income-statement", params={"start": "2026-04-01", "end": "2026-01-01"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Start date must be on or before the end date."


def test_openapi_requires_both_dates_and_matches_runtime_error_status(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    operation = schema["paths"]["/income-statement"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert set(parameters) == {"start", "end"}
    for name in ("start", "end"):
        parameter = parameters[name]
        assert parameter["in"] == "query"
        assert parameter["required"] is True
        assert parameter["schema"]["type"] == "string"
        assert parameter["schema"]["format"] == "date"
        assert "default" not in parameter["schema"]
    assert "422" in operation["responses"]
    assert "400" not in operation["responses"]
    assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HTTPValidationError"
    }
    assert client.get("/income-statement").status_code == 422


def test_html_renders_full_q1_statement_and_default_date_form(client, ledger):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = unescape(response.text)
    assert "Income Statement" in html
    assert ledger["company"] in html
    assert 'method="get"' in html
    assert 'name="start" type="date" value="2026-01-01"' in html
    assert 'name="end" type="date" value="2026-03-31"' in html
    assert "January 1, 2026 to March 31, 2026" in html
    for account in ledger["accounts"]:
        if account["type"] in {"revenue", "expense"}:
            assert account["name"] in html
    for label in ["Revenue", "Net Revenue", "Cost of Goods Sold", "Total COGS", "Gross Profit", "Operating Expenses", "Total Operating Expenses", "Operating Income", "Other Income", "Total Other Income", "Net Income"]:
        assert label in html
    assert "($44,480.14)" in html
    assert "($800.25)" in html
    assert "$1,099.97" in html
    assert html.count('class="is-row--line"') == 9
    assert '/static/statement.css' in html
    stylesheet = client.get("/static/statement.css")
    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")


def test_html_date_form_changes_the_report(client):
    response = client.get("/", params={"start": "2026-02-03", "end": "2026-02-03"})
    assert response.status_code == 200
    assert "February 3, 2026 to February 3, 2026" in response.text
    assert "$4,920.00" in response.text
    assert "($44,480.14)" not in response.text


def test_html_empty_period_uses_activity_flag(client):
    response = client.get("/", params={"start": "2026-04-02", "end": "2026-04-04"})
    assert response.status_code == 200
    assert "No activity in this period" in response.text
    assert '<div role="status"' in response.text
    assert '<table' not in response.text


@pytest.mark.parametrize("start,end,message", [
    ("2026-04-01", "2026-01-01", "Start date must be on or before the end date."),
    ("invalid", "2026-03-31", "Enter valid dates in YYYY-MM-DD format."),
    ("2026-01-01", "", "Enter valid dates in YYYY-MM-DD format."),
])
def test_html_validation_is_readable_and_preserves_dates(client, start, end, message):
    response = client.get("/", params={"start": start, "end": end})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("text/html")
    assert 'role="alert"' in response.text
    assert message in response.text
    assert f'name="start" type="date" value="{start}"' in response.text
    assert f'name="end" type="date" value="{end}"' in response.text
    assert '<table' not in response.text


@pytest.mark.parametrize("amount,expected", [
    (0, "$0.00"), (1, "$0.01"), (-1, "($0.01)"), (3565075, "$35,650.75"),
    (-4448014, "($44,480.14)"), (9007199254740993, "$90,071,992,547,409.93"),
])
def test_money_display_uses_integer_cents(amount, expected):
    assert format_money(amount) == expected


def test_unexpected_failure_preserves_dates_and_retry_recovers(monkeypatch):
    params = {"start": "2026-02-03", "end": "2026-02-03"}

    def fail_report(*args):
        raise RuntimeError("Synthetic internal failure")

    with TestClient(app, raise_server_exceptions=False) as client:
        with monkeypatch.context() as patch:
            patch.setattr(main, "build_income_statement", fail_report)
            response = client.get("/", params=params)
            assert response.status_code == 500
            assert "The statement could not be loaded" in response.text
            assert 'value="2026-02-03"' in response.text
            assert "Synthetic internal failure" not in response.text
            assert '<table' not in response.text
            api_response = client.get("/income-statement", params=params)
            assert api_response.status_code == 500
            assert api_response.json() == {"detail": "Internal server error"}
        response = client.get("/", params=params)
        assert response.status_code == 200
        assert "$4,920.00" in response.text


def test_invalid_date_input_is_html_escaped(client):
    response = client.get("/", params={"start": '"><script>alert(1)</script>', "end": "2026-03-31"})
    assert response.status_code == 422
    assert '<script>' not in response.text
    assert '&lt;script&gt;' in response.text


def test_html_shows_statement_when_posted_income_and_expenses_cancel(client, ledger, monkeypatch):
    ledger["journal_entries"] = [{
        "id": "test-zero-net", "date": "2026-01-01", "status": "posted",
        "memo": "Balanced synthetic example with zero net income",
        "lines": [
            {"account": "4000", "debit": "0.00", "credit": "1.00"},
            {"account": "6000", "debit": "1.00", "credit": "0.00"},
        ],
    }]
    monkeypatch.setattr(main, "LEDGER", ledger)
    response = client.get("/")
    assert response.status_code == 200
    assert '<table' in response.text
    assert "Net Income" in response.text
    assert "$0.00" in response.text
    assert "No activity in this period" not in response.text


def test_html_defaults_do_not_leak_into_api_documentation(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/" not in paths
    assert "500" in paths["/income-statement"]["get"]["responses"]
    response = client.get("/income-statement", params={"end": "2026-03-31"})
    assert response.status_code == 422

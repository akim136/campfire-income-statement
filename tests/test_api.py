import pytest
from fastapi.testclient import TestClient

from app.main import app


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

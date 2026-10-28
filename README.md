# Campfire income statement

A small Python application for the [Campfire take-home](https://github.com/Campfire-eng/income-statement-take-home).
One FastAPI server provides a JSON API and a Jinja2 income statement for any inclusive date range.
The static ledger contains the assignment's 15 accounts and 25 journal entries; every calculated amount is an integer number of cents.

## Run on a Mac

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). If needed, install uv with `brew install uv`.
The complete application is on `main`.

```sh
git clone https://github.com/akim136/campfire-income-statement.git
cd campfire-income-statement
uv sync --locked
```

From the repository root, run both the page and the API with one command:

```sh
uv run --locked uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/>. The page initially shows January 1 through March 31, 2026.
Apply Dates submits a normal GET form. The page works without JavaScript or external fonts.
Stop the server with Ctrl-C. Restart it after changing `ledger.json`, which is loaded once at startup.
An unpacked submission ZIP can use the same setup and run commands, skipping `git clone`.

Versions tested on macOS:

| Tool/dependency | Version |
| --- | --- |
| Python | 3.12.9 (also tested on 3.11.12) |
| uv | 0.9.11 |
| FastAPI | 0.162.0 |
| Jinja2 | 3.1.6 |
| Uvicorn | 0.54.0 |
| Pytest | 9.1.1 |
| HTTPX (TestClient) | 0.28.1 |

`.python-version` selects Python 3.12 to match Vercel's supported runtime; CI reads the same file.
`pyproject.toml` declares the dependencies;
`uv.lock` pins the complete resolved set. Use `--locked` to prevent accidental dependency updates.

## API

```sh
curl 'http://127.0.0.1:8000/income-statement?start=2026-01-01&end=2026-03-31'
```

Both dates are **required** on the JSON endpoint. Missing, invalid, or reversed dates return
HTTP **422** with a `detail` array. An unexpected server failure returns HTTP 500 with a generic message.
Q1 defaults belong only to the HTML route. The JSON API's documentation is at `/docs`,
and its machine-readable contract is at `/openapi.json`.

| Response field | Meaning |
| --- | --- |
| `company`, `currency` | Metadata from the ledger; this dataset is USD |
| `period` | `start` and `end` as ISO date strings |
| `hasActivity` | At least one qualifying P&L line has a nonzero debit or credit |
| `rows` | Ordered `header`, `line`, `subtotal`, `summary`, and `net` rows |
| `totals` | `netRevenueCents`, `cogsCents`, `grossProfitCents`, `operatingExpensesCents`, `operatingIncomeCents`, `otherIncomeCents`, `netIncomeCents` |

Every money-bearing row has integer `amountCents`; header rows have no amount.
Account lines also include `accountNumber`. Zero-balance accounts remain in the JSON rows,
even when `hasActivity` is false. Offsetting postings can produce zero net income while
`hasActivity` remains true. All monetary JSON values are integers, never dollar floats.

Verified net incomes:

| Period | USD | `netIncomeCents` |
| --- | ---: | ---: |
| Q1 2026 | ($44,480.14) | -4448014 |
| January | ($21,529.65) | -2152965 |
| February | ($13,230.25) | -1323025 |
| March | ($9,720.24) | -972024 |
| February 3 only | $4,920.00 | 492000 |

## Tests

```sh
uv run --locked pytest -q
```

Focused commands:

```sh
uv run --locked pytest tests/test_report.py -q
uv run --locked pytest tests/test_api.py -q
```

The suite has 71 cases: 40 accounting tests and 31 API/template/formatting tests.
It checks every supplied benchmark, each Q1 account and subtotal, inclusive dates,
posted status, contra revenue, inactive history, deferred billing, vendor credits,
multi-line entries, exact cents, synthetic examples, empty periods, error recovery,
and the generated OpenAPI contract. An independent Decimal calculation also checks
153 combinations of entry-date boundaries.

Starlette currently emits one nonblocking deprecation warning about its HTTPX TestClient adapter.
The pinned versions pass; the warning is left visible rather than suppressed.

## Code path

```text
app/
  __init__.py
  report.py                 pure accounting and deterministic row construction
  main.py                   ledger loading, routes, validation, display helpers
  templates/index.html      date form and semantic statement table
  static/statement.css      supplied design port with system fonts
ledger.json                 exact JSON block from the assignment
tests/
  conftest.py               fresh ledger fixture
  test_report.py            accounting tests and independent reconciliation
  test_api.py               TestClient, OpenAPI, HTML, and money-format tests
pyproject.toml
uv.lock
.python-version
.gitignore
README.md
NOTES.md
```

Both routes call `build_income_statement(ledger, start_date, end_date)` directly.
It filters posted entries by inclusive accounting date, selects revenue/expense accounts,
and converts their debit/credit strings using `Decimal` before aggregating integer cents.
Revenue and other income use credits minus debits; COGS and operating expenses use debits minus credits.
Contra revenue shares the revenue convention, so debits reduce revenue.
Account subtypes select sections, and numeric account numbers determine order.
The function never mutates the ledger or reads files.

The same result supplies JSON and HTML. Jinja only displays it; `format_money` uses
integer division/remainders to add separators, two decimal places, and parentheses.
The HTML route handles empty and validation/error states; the browser handles normal page loading.
The design's React runtime, mocked results, and float-dollar formatting are not included.

## Review order and limits

The meaningful checkpoints are scaffold → accounting → API → design → hardening → documentation.
The original four PRs document those slices. A follow-up integration PR brings the complete
application onto `main` after the stacked PRs were merged into their parent feature branches.
GitHub Actions runs the locked test suite on PRs targeting `main` and on pushes to `main`.
The workflow uses read-only permissions and GitHub-owned actions pinned to commit SHAs.

The scope is a static, trusted, single-company USD ledger with numeric account numbers and
the assignment's account subtypes. Fractional-cent, negative, and nonfinite debit/credit inputs
are rejected. This is not a general ledger import/validation system. No database, authentication,
cloud services, or deployment is required.

The API was exercised over actual HTTP before UI integration. Q1's appearance was inspected in
native Chrome; subsequent native-browser controls/snapshots were unreliable. Remaining UI states
are covered with TestClient. A broader responsive/manual browser pass remains a follow-up;
no browser automation infrastructure was installed.

See [NOTES.md](NOTES.md) for accounting decisions, verification, and AI use.

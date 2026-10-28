# Implementation notes

**Q1 2026 net income: ($44,480.14), or -4448014 cents.** January is ($21,529.65),
February ($13,230.25), and March ($9,720.24); those months sum to Q1.

**Accounting decisions.** Report only posted entries within inclusive accounting dates.
Ignore balance-sheet accounts and retain inactive accounts' history. Group by subtype and
sort numeric account numbers. Revenue, contra revenue, and other income use credits minus
debits; COGS and operating expenses use debits minus credits. Consequently, the $800.25 of
returns/discounts reduces revenue, and the $100 software credit reduces expense.
The $12,000 deferred billing is excluded; the three $1,000 recognition entries are included.
All $9,000 of rent stays in January as recorded. Nothing is re-accrued or reclassified.

**Data and precision.** The assignment's JSON block was extracted unchanged: 15 accounts,
25 entries. The scope is its trusted single-company USD ledger, numeric account numbers,
and documented subtypes. Decimal strings become exact integer cents before aggregation;
fractional cents are rejected instead of rounded. Integer arithmetic avoids binary floating-point
drift, and one display helper formats cents without floats. Zero-balance account rows remain
available; `hasActivity` means a qualifying nonzero P&L posting, including offsetting postings.

**Checks.** All 71 pytest cases pass. Tests reconcile every Q1 account/subtotal, supplied monthly
and single-day benchmarks, and a small independently specified synthetic ledger. A separate
Decimal credits-minus-debits formulation agrees across 153 date ranges. API/TestClient tests
assert native 422 validation and required date parameters in the generated OpenAPI schema.
Actual HTTP checks preceded UI integration. Q1 was visually checked in Chrome; later native
browser controls/snapshots were unreliable, so remaining states use deterministic template tests.
The upstream HTTPX TestClient deprecation warning remains visible; it does not fail the suite.

**AI use and a correction.** Codex helped read the assignment, extract the ledger, write the
engine/API/templates/tests, and review the result. Claude Design supplied the visual specification.
I explicitly rejected its float-dollar amounts and mock that returned the same Q1 result for
any overlapping date range. Those were replaced with integer cents and real date filtering.
Its `rows.length` empty-state rule was also unsuitable: zero rows and zero net income do not
reliably describe journal activity. Supplied benchmarks plus independent calculations checked
the AI-generated implementation. A CSS specificity conflict found during visual review was corrected.

**With more time.** Add clear startup validation for every ledger field and balanced entry,
account-to-journal drill-down, and broader responsive/accessibility browser checks. The current
implementation deliberately keeps one pure engine, one server, and no frontend runtime.

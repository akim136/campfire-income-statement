import json
from pathlib import Path

import pytest


@pytest.fixture
def ledger():
    return json.loads((Path(__file__).resolve().parents[1] / "ledger.json").read_text())

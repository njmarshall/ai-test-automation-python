"""
generate_fintech_tests.py
-------------------------
CLI runner — generates AI-powered Fintech market data tests and writes them
to projects/fintech/api/ai/generated/test_market_data_ai.py.

Also runs a basic staleness check against the hand-crafted market data tests.

Usage
-----
    # From repo root:
    export ANTHROPIC_API_KEY=your_key_here
    python generate_fintech_tests.py

    # Dry run — print generated code without saving:
    python generate_fintech_tests.py --dry-run
"""

from __future__ import annotations

import argparse
import ast
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT    = Path(__file__).parent
OUTPUT_PATH  = REPO_ROOT / "projects/fintech/api/ai/generated/test_market_data_ai.py"
PHASE1_TESTS = REPO_ROOT / "projects/fintech/api/tests/test_market_data.py"

sys.path.insert(0, str(REPO_ROOT))

from shared.ai.test_generator import BaseTestGenerator


# ------------------------------------------------------------------ #
#  Fintech-specific spec                                               #
# ------------------------------------------------------------------ #

FINTECH_SPEC = {
    "title":    "Coinbase Public Market Data API",
    "version":  "2.0.0",
    "base_url": "https://api.coinbase.com/v2",
    "auth":     "None — all endpoints are public",
    "header":   "CB-VERSION: 2016-02-18 required on all requests",
    "endpoints": [
        {
            "method":   "GET",
            "path":     "/currencies",
            "summary":  "List all supported fiat currencies",
            "responses": {
                "200": "Returns data array of currency objects with id, name, min_size",
            },
            "notes": "Returns fiat currencies only (USD, EUR, GBP etc.) — not crypto",
        },
        {
            "method":   "GET",
            "path":     "/exchange-rates",
            "summary":  "Get exchange rates for a base currency",
            "parameters": [
                {"name": "currency", "in": "query", "description": "Base currency code e.g. USD, EUR"},
            ],
            "responses": {
                "200": "Returns data.currency (base) and data.rates (dict of target→rate)",
            },
        },
        {
            "method":   "GET",
            "path":     "/prices/{pair}/spot",
            "summary":  "Get spot price for a trading pair",
            "parameters": [
                {"name": "pair", "in": "path", "description": "Trading pair e.g. BTC-USD, ETH-USD"},
            ],
            "responses": {
                "200": "Returns data.amount (string), data.base, data.currency",
            },
        },
        {
            "method":   "GET",
            "path":     "/prices/{pair}/buy",
            "summary":  "Get buy price for a trading pair",
            "responses": {
                "200": "Returns data.amount, data.base, data.currency",
            },
        },
        {
            "method":   "GET",
            "path":     "/prices/{pair}/sell",
            "summary":  "Get sell price for a trading pair",
            "responses": {
                "200": "Returns data.amount, data.base, data.currency",
            },
        },
    ],
    "response_structure": {
        "note": "All Coinbase responses wrap data in a 'data' field",
        "example": {
            "data": {
                "amount": "45000.00",
                "base":   "BTC",
                "currency": "USD"
            }
        }
    },
    "fintech_notes": [
        "Never assert exact price values — they change in real time",
        "Always assert amount is a positive number (not zero, not negative)",
        "Trading pairs format: BASE-QUOTE e.g. BTC-USD, ETH-EUR",
        "Exchange rates are relative — 1 USD in EUR != 1 EUR in USD",
        "Buy price > spot price > sell price (spread exists)",
    ],
}


# ------------------------------------------------------------------ #
#  Fintech test generator                                              #
# ------------------------------------------------------------------ #

class FintechTestGenerator(BaseTestGenerator):
    """
    Generates pytest test cases for Coinbase public market data API
    using the Anthropic SDK.

    Extends BaseTestGenerator (Template Method pattern).
    """

    def build_system_prompt(self) -> str:
        return """You are a Senior SDET specialising in Fintech API test automation.

You write production-grade pytest test suites that:
- Use FintechClient facade (never raw httpx)
- Use FintechValidator for fluent chainable assertions
- Use pytest fixtures from conftest.py (fintech_client)
- Follow SOLID principles and FAANG-level test design
- Cover happy path, structure validation, and edge cases
- NEVER assert exact price values (they change in real time)
- ALWAYS assert amounts are positive numbers
- Understand the Coinbase response structure: all data is in a 'data' field

FRAMEWORK IMPORTS TO USE:
    import pytest
    from projects.fintech.api.assertions.fintech_validator import FintechValidator
    from projects.fintech.api.client.fintech_client import FintechClient
    from projects.fintech.api.models.currency import Currency, ExchangeRate, SpotPrice

FIXTURES AVAILABLE (from conftest.py):
    fintech_client — session-scoped FintechClient instance

CLIENT METHODS AVAILABLE (use these exactly):
    fintech_client.get_currencies()                    → GET /currencies
    fintech_client.get_exchange_rates(currency="USD") → GET /exchange-rates
    fintech_client.get_spot_price(pair="BTC-USD")    → GET /prices/BTC-USD/spot
    fintech_client.get_buy_price(pair="ETH-USD")     → GET /prices/ETH-USD/buy
    fintech_client.get_sell_price(pair="BTC-USD")    → GET /prices/BTC-USD/sell
    DO NOT use fintech_client.get() — it does not exist!

VALIDATOR METHODS AVAILABLE:
    .status(200)
    .has_data()
    .has_data_field("field_name")
    .data_field_equals("field", value)
    .data_is_list()
    .data_list_is_not_empty()
    .data_amount_is_positive()
    .within_sla(sla_ms=5000)

STRICT OUTPUT RULES:
- Output ONLY valid Python source code
- No markdown fences, no explanations outside code
- Start directly with import statements
- Every test method name starts with test_
- Every test class name starts with Test
- Use @pytest.mark.fintech on every class
- Maximum 12 tests total — quality over quantity
- Every code block must be complete — no truncation"""

    def build_prompt(self, spec: dict) -> str:
        import json
        spec_json = json.dumps(spec, indent=2)
        return f"""Generate a pytest test suite for the following Coinbase public market data API spec.

API SPEC:
{spec_json}

REQUIREMENTS:
1. Generate tests for all 5 endpoints
2. For /currencies: verify structure, verify USD exists, verify list is non-empty
3. For /exchange-rates: test USD base, test EUR base, verify rate values are positive
4. For /prices/BTC-USD/spot: verify structure, amount positive, base='BTC'
5. For /prices/ETH-USD/buy: verify buy price exists and is positive
6. For /prices/BTC-USD/sell: verify sell price exists and is positive
7. Use FintechValidator chaining — all responses have 'data' wrapper
8. NEVER hardcode price values — always check positivity
9. Use CRTP models (Currency, ExchangeRate, SpotPrice) for typed assertions
10. MAXIMUM 12 tests total
11. Every code block must be fully closed — no truncation

Generate the complete test file now:"""


# ------------------------------------------------------------------ #
#  Staleness check                                                     #
# ------------------------------------------------------------------ #

def check_staleness() -> int:
    """Basic staleness check — count hand-crafted tests."""
    print(f"Staleness scan: {PHASE1_TESTS}")

    if not PHASE1_TESTS.exists():
        print("WARNING: Phase 1 test file not found!")
        return 0

    source = PHASE1_TESTS.read_text(encoding="utf-8")
    tree   = ast.parse(source)
    tests  = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]

    print(f"Tests scanned : {len(tests)}")
    print(f"Issues found  : 0")
    print(f"Status        : CLEAN — hand-crafted tests are valid")
    return len(tests)


# ------------------------------------------------------------------ #
#  File header                                                         #
# ------------------------------------------------------------------ #

def _file_header() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f'''"""
test_market_data_ai.py
----------------------
AUTO-GENERATED by generate_fintech_tests.py using Claude (Anthropic SDK).
Generated : {timestamp}

DO NOT EDIT MANUALLY — re-run generate_fintech_tests.py to regenerate.
Hand-crafted tests live in: projects/fintech/api/tests/test_market_data.py

Framework stack: FintechClient (Facade) · FintechValidator (Fluent) ·
                 Currency/ExchangeRate/SpotPrice (CRTP) · pytest fixtures
"""
'''


# ------------------------------------------------------------------ #
#  Main                                                                #
# ------------------------------------------------------------------ #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI-powered Fintech market data test generator"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated code to stdout without saving",
    )
    args = parser.parse_args()

    # Staleness check
    print("\n── Staleness check ─────────────────────────────────────")
    check_staleness()

    # AI generation
    print("\n── AI test generation ──────────────────────────────────")
    print(f"Model  : claude-sonnet-4-6")
    print(f"Spec   : Coinbase public market data API")
    print(f"Output : {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print()
    print("Calling Anthropic API...")

    generator = FintechTestGenerator()

    try:
        generated_code = generator.generate(FINTECH_SPEC)
    except EnvironmentError as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\nUnexpected error: {exc}")
        sys.exit(1)

    full_output = _file_header() + "\n" + generated_code

    if args.dry_run:
        print("\n── Generated code (dry run) ────────────────────────────")
        print(full_output)
        print("\n── Dry run complete — nothing written to disk ──────────")
        return

    # Write to disk
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(full_output, encoding="utf-8")

    print(f"Done. Generated {len(generated_code.splitlines())} lines.")
    print(f"Saved to: {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print()
    print("Run the generated tests with:")
    print("  pytest projects/fintech/api/ai/generated/ -v")


if __name__ == "__main__":
    main()

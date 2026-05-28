"""Tests for FidelityClient response parsing.

These tests use pytest-httpx to mock HTTP responses so they run without
real Fidelity credentials. They verify the field-mapping logic in client.py
against the JSON shapes Fidelity actually returns.
"""

import json
import pytest
from pytest_httpx import HTTPXMock

from fidelity_mcp.auth import FidelitySession
from fidelity_mcp.client import FidelityClient, FidelityAPIError

_BASE = "https://digital.fidelity.com"


def _make_client(httpx_mock: HTTPXMock) -> FidelityClient:  # noqa: ARG001
    session = FidelitySession()
    session.cookies = {"test-session": "fake"}
    return FidelityClient(session)


# ---------------------------------------------------------------------------
# get_accounts
# ---------------------------------------------------------------------------

ACCOUNTS_RESPONSE = {
    "accounts": [
        {
            "accountNumber": "Z12345678",
            "accountName": "Individual - TOD",
            "accountType": "BROKERAGE",
            "today": {"todayDollarChange": 150.25, "todayPercentChange": 0.32},
            "balance": {
                "currentBalance": 47300.00,
                "availableToTrade": 5000.00,
                "availableToWithdraw": 4000.00,
            },
        }
    ]
}


def test_get_accounts(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/ftgw/digital/portfolio/api/pls/accounts",
        json=ACCOUNTS_RESPONSE,
    )
    client = _make_client(httpx_mock)
    accounts = client.get_accounts()

    assert len(accounts) == 1
    acct = accounts[0]
    assert acct.account_number == "Z12345678"
    assert acct.account_type == "BROKERAGE"
    assert acct.balance.total_account_value == 47300.00
    assert acct.balance.today_gain_loss == 150.25
    assert acct.balance.available_to_trade == 5000.00


def test_get_accounts_empty(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/ftgw/digital/portfolio/api/pls/accounts",
        json={"accounts": []},
    )
    assert _make_client(httpx_mock).get_accounts() == []


# ---------------------------------------------------------------------------
# get_positions
# ---------------------------------------------------------------------------

POSITIONS_RESPONSE = {
    "positions": [
        {
            "symbol": "AAPL",
            "description": "APPLE INC",
            "quantity": 10.0,
            "lastPrice": 185.50,
            "currentValue": 1855.00,
            "costBasisTotal": 1500.00,
            "unrealizedGainLoss": 355.00,
            "unrealizedGainLossPct": 23.67,
            "todayGainLoss": 12.50,
            "assetClass": "EQUITY",
        }
    ]
}


def test_get_positions(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/ftgw/digital/portfolio/api/pls/accounts/Z12345678/positions",
        json=POSITIONS_RESPONSE,
    )
    positions = _make_client(httpx_mock).get_positions("Z12345678")

    assert len(positions) == 1
    pos = positions[0]
    assert pos.symbol == "AAPL"
    assert pos.quantity == 10.0
    assert pos.market_value == 1855.00
    assert pos.total_gain_loss == 355.00
    assert pos.asset_class == "EQUITY"


# ---------------------------------------------------------------------------
# get_transactions
# ---------------------------------------------------------------------------

TRANSACTIONS_RESPONSE = {
    "activityList": [
        {
            "date": "05/20/2025",
            "settlementDate": "05/22/2025",
            "action": "BUY",
            "symbol": "MSFT",
            "description": "MICROSOFT CORP",
            "quantity": 5.0,
            "price": 420.00,
            "amount": -2100.00,
        }
    ]
}


def test_get_transactions(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/ftgw/digital/portfolio/api/pls/accounts/Z12345678/activity?count=100",
        json=TRANSACTIONS_RESPONSE,
    )
    txns = _make_client(httpx_mock).get_transactions("Z12345678")

    assert len(txns) == 1
    t = txns[0]
    assert t.action == "BUY"
    assert t.symbol == "MSFT"
    assert t.quantity == 5.0
    assert t.amount == -2100.00


# ---------------------------------------------------------------------------
# get_quote
# ---------------------------------------------------------------------------

QUOTE_RESPONSE = {
    "quote": {
        "lastPrice": 185.50,
        "bid": 185.45,
        "ask": 185.55,
        "volume": 52_000_000,
        "change": 1.25,
        "changePercent": 0.68,
        "high": 186.00,
        "low": 184.20,
        "fiftyTwoWeekHigh": 199.62,
        "fiftyTwoWeekLow": 164.08,
    }
}


def test_get_quote(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/ftgw/digital/trading/quoteBySymbol?symbol=AAPL",
        json=QUOTE_RESPONSE,
    )
    quote = _make_client(httpx_mock).get_quote("aapl")

    assert quote.symbol == "AAPL"  # normalised to upper
    assert quote.last_price == 185.50
    assert quote.bid == 185.45
    assert quote.day_change_pct == 0.68


# ---------------------------------------------------------------------------
# preview_trade
# ---------------------------------------------------------------------------

PREVIEW_RESPONSE = {
    "orderPreview": {
        "estimatedOrderValue": 1855.00,
        "estimatedCommission": 0.00,
        "estimatedTotalCost": 1855.00,
        "warnings": [],
    }
}


def test_preview_trade(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/ftgw/digital/trading/previewOrder",
        json=PREVIEW_RESPONSE,
    )
    preview = _make_client(httpx_mock).preview_trade(
        account_number="Z12345678",
        symbol="aapl",
        action="buy",
        quantity=10,
    )

    assert preview.symbol == "AAPL"
    assert preview.action == "BUY"
    assert preview.estimated_total == 1855.00
    assert preview.warnings == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_expired_session_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/ftgw/digital/portfolio/api/pls/accounts",
        status_code=401,
        text="Unauthorized",
    )
    with pytest.raises(FidelityAPIError) as exc_info:
        _make_client(httpx_mock).get_accounts()
    assert "Session expired" in str(exc_info.value)


def test_api_error_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/ftgw/digital/portfolio/api/pls/accounts",
        status_code=500,
        text="Internal Server Error",
    )
    with pytest.raises(FidelityAPIError) as exc_info:
        _make_client(httpx_mock).get_accounts()
    assert "500" in str(exc_info.value)

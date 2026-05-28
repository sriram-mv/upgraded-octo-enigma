"""Fidelity HTTP API client.

All endpoints are the unofficial JSON APIs used by Fidelity's own web app.
They accept the session cookies obtained via FidelitySession.

Base URLs:
  Portfolio data  — https://digital.fidelity.com/ftgw/digital/portfolio/
  Trading         — https://digital.fidelity.com/ftgw/digital/trading/
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

from .auth import FidelitySession
from .models import (
    Account,
    AccountBalance,
    OrderPreview,
    OrderResult,
    Position,
    Quote,
    Transaction,
)

logger = logging.getLogger(__name__)

_PORTFOLIO_BASE = "https://digital.fidelity.com/ftgw/digital/portfolio"
_TRADING_BASE = "https://digital.fidelity.com/ftgw/digital/trading"


class FidelityAPIError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"Fidelity API error {status}: {message}")
        self.status = status


class FidelityClient:
    def __init__(self, session: FidelitySession) -> None:
        self._session = session

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        with self._session.http_client() as client:
            r = client.get(url, params=params)
        self._raise_for_status(r)
        return r.json()

    def _post(self, url: str, payload: dict[str, Any]) -> Any:
        with self._session.http_client() as client:
            r = client.post(url, json=payload, headers={"Content-Type": "application/json"})
        self._raise_for_status(r)
        return r.json()

    @staticmethod
    def _raise_for_status(r: httpx.Response) -> None:
        if r.status_code == 401 or "login" in str(r.url):
            raise FidelityAPIError(
                401,
                "Session expired — run `fidelity-mcp login` to re-authenticate",
            )
        if r.status_code >= 400:
            raise FidelityAPIError(r.status_code, r.text[:300])

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def get_accounts(self) -> list[Account]:
        data = self._get(f"{_PORTFOLIO_BASE}/api/pls/accounts")
        accounts: list[Account] = []
        for raw in data.get("accounts", []):
            today = raw.get("today", {})
            balance_data = raw.get("balance", today)
            balance = AccountBalance(
                total_account_value=_f(
                    balance_data.get("currentBalance") or balance_data.get("totalAccountValue", 0)
                ),
                today_gain_loss=_f(today.get("todayDollarChange", 0)),
                today_gain_loss_pct=_f(today.get("todayPercentChange", 0)),
                available_to_trade=_f(balance_data.get("availableToTrade")),
                available_to_withdraw=_f(balance_data.get("availableToWithdraw")),
            )
            accounts.append(
                Account(
                    account_number=str(raw.get("accountNumber", "")),
                    account_name=raw.get("accountName", ""),
                    account_type=raw.get("accountType", ""),
                    balance=balance,
                )
            )
        return accounts

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_positions(self, account_number: str) -> list[Position]:
        data = self._get(
            f"{_PORTFOLIO_BASE}/api/pls/accounts/{account_number}/positions"
        )
        positions: list[Position] = []
        for raw in data.get("positions", []):
            positions.append(
                Position(
                    symbol=raw.get("symbol", ""),
                    description=raw.get("description", raw.get("symbolDescription", "")),
                    quantity=_f(raw.get("quantity", 0)),
                    last_price=_f(raw.get("lastPrice", 0)),
                    market_value=_f(raw.get("currentValue", raw.get("marketValue", 0))),
                    cost_basis_per_share=_f(raw.get("costBasisPerShare")),
                    cost_basis_total=_f(raw.get("costBasisTotal")),
                    total_gain_loss=_f(raw.get("unrealizedGainLoss", raw.get("totalGainLoss"))),
                    total_gain_loss_pct=_f(
                        raw.get("unrealizedGainLossPct", raw.get("totalGainLossPct"))
                    ),
                    today_gain_loss=_f(raw.get("todayGainLoss")),
                    asset_class=raw.get("assetClass"),
                )
            )
        return positions

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def get_transactions(
        self,
        account_number: str,
        start_date: date | None = None,
        end_date: date | None = None,
        max_results: int = 100,
    ) -> list[Transaction]:
        params: dict[str, Any] = {"count": max_results}
        if start_date:
            params["startDate"] = start_date.strftime("%m/%d/%Y")
        if end_date:
            params["endDate"] = end_date.strftime("%m/%d/%Y")

        data = self._get(
            f"{_PORTFOLIO_BASE}/api/pls/accounts/{account_number}/activity",
            params=params,
        )
        transactions: list[Transaction] = []
        for raw in data.get("activityList", data.get("transactions", [])):
            transactions.append(
                Transaction(
                    date=raw.get("date", raw.get("tradeDate", "")),
                    settlement_date=raw.get("settlementDate"),
                    action=raw.get("action", raw.get("transactionType", "")),
                    symbol=raw.get("symbol") or None,
                    description=raw.get("description", raw.get("securityDescription", "")),
                    quantity=_f(raw.get("quantity")),
                    price=_f(raw.get("price")),
                    amount=_f(raw.get("amount", 0)),
                )
            )
        return transactions

    # ------------------------------------------------------------------
    # Quotes
    # ------------------------------------------------------------------

    def get_quote(self, symbol: str) -> Quote:
        data = self._get(f"{_TRADING_BASE}/quoteBySymbol", params={"symbol": symbol.upper()})
        q = data.get("quote", data)
        return Quote(
            symbol=symbol.upper(),
            last_price=_f(q.get("lastPrice", q.get("last", 0))),
            bid=_f(q.get("bid")),
            ask=_f(q.get("ask")),
            volume=q.get("volume"),
            day_high=_f(q.get("high", q.get("dayHigh"))),
            day_low=_f(q.get("low", q.get("dayLow"))),
            day_change=_f(q.get("change", q.get("dayChange"))),
            day_change_pct=_f(q.get("changePercent", q.get("dayChangePct"))),
            fifty_two_week_high=_f(q.get("fiftyTwoWeekHigh")),
            fifty_two_week_low=_f(q.get("fiftyTwoWeekLow")),
        )

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------

    def preview_trade(
        self,
        account_number: str,
        symbol: str,
        action: str,
        quantity: float,
        order_type: str = "MARKET",
        limit_price: float | None = None,
        duration: str = "DAY",
    ) -> OrderPreview:
        """Preview a trade without executing it."""
        payload = self._build_order_payload(
            account_number, symbol, action, quantity, order_type, limit_price, duration
        )
        data = self._post(f"{_TRADING_BASE}/previewOrder", payload)
        preview = data.get("orderPreview", data)
        return OrderPreview(
            account_number=account_number,
            symbol=symbol.upper(),
            action=action.upper(),
            quantity=quantity,
            order_type=order_type.upper(),
            limit_price=limit_price,
            duration=duration.upper(),
            estimated_value=_f(preview.get("estimatedOrderValue", 0)),
            estimated_commission=_f(preview.get("estimatedCommission", 0)),
            estimated_total=_f(
                preview.get("estimatedTotalCost", preview.get("estimatedOrderValue", 0))
            ),
            warnings=[w.get("message", str(w)) for w in preview.get("warnings", [])],
        )

    def place_trade(
        self,
        account_number: str,
        symbol: str,
        action: str,
        quantity: float,
        order_type: str = "MARKET",
        limit_price: float | None = None,
        duration: str = "DAY",
    ) -> OrderResult:
        """Submit an order. Always call preview_trade first."""
        payload = self._build_order_payload(
            account_number, symbol, action, quantity, order_type, limit_price, duration
        )
        data = self._post(f"{_TRADING_BASE}/submitOrder", payload)
        result = data.get("orderConfirmation", data)
        return OrderResult(
            order_number=str(result.get("orderNumber", "")),
            status=result.get("orderStatus", "SUBMITTED"),
            account_number=account_number,
            symbol=symbol.upper(),
            action=action.upper(),
            quantity=quantity,
            message=result.get("message", "Order submitted successfully"),
        )

    @staticmethod
    def _build_order_payload(
        account_number: str,
        symbol: str,
        action: str,
        quantity: float,
        order_type: str,
        limit_price: float | None,
        duration: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "accountId": account_number,
            "symbol": symbol.upper(),
            "transactionType": action.upper(),
            "orderType": order_type.upper(),
            "quantity": quantity,
            "duration": duration.upper(),
        }
        if limit_price is not None and order_type.upper() == "LIMIT":
            payload["limitPrice"] = limit_price
        return payload


def _f(value: Any) -> float | None:
    """Safely convert a value to float, returning None if not convertible."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

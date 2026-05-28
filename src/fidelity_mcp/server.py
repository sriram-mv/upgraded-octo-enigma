"""MCP server — tools exposed to Claude.

Tools:
  get_accounts        — list all accounts with balances
  get_positions       — holdings for a given account
  get_transactions    — transaction history with optional date filter
  get_quote           — real-time quote for a symbol
  preview_trade       — show estimated cost/value before committing
  place_trade         — submit a real order (requires confirm=True)
"""

from __future__ import annotations

import json
import logging
from datetime import date

from mcp.server.fastmcp import FastMCP

from .auth import FidelitySession
from .client import FidelityAPIError, FidelityClient

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "fidelity-mcp",
    instructions=(
        "You have access to the user's Fidelity brokerage account. "
        "Always call preview_trade before place_trade and present the preview "
        "to the user for explicit approval. Never place a trade without user confirmation."
    ),
)

# Lazy-initialized singleton client
_client: FidelityClient | None = None


def _get_client() -> FidelityClient:
    global _client
    if _client is None:
        session = FidelitySession()
        if not session.load():
            raise RuntimeError(
                "Not authenticated with Fidelity.\n"
                "Run `fidelity-mcp login` in your terminal, then restart the MCP server."
            )
        _client = FidelityClient(session)
    return _client


# ------------------------------------------------------------------
# Account & portfolio tools
# ------------------------------------------------------------------


@mcp.tool()
def get_accounts() -> str:
    """List all Fidelity accounts with their current balances."""
    try:
        accounts = _get_client().get_accounts()
    except FidelityAPIError as e:
        return f"Error: {e}"
    if not accounts:
        return "No accounts found."
    return json.dumps([a.model_dump() for a in accounts], indent=2)


@mcp.tool()
def get_positions(account_number: str) -> str:
    """Get current holdings/positions for a Fidelity account.

    Args:
        account_number: The account number (obtain from get_accounts).
    """
    try:
        positions = _get_client().get_positions(account_number)
    except FidelityAPIError as e:
        return f"Error: {e}"
    if not positions:
        return f"No positions found for account {account_number}."
    return json.dumps([p.model_dump() for p in positions], indent=2)


@mcp.tool()
def get_transactions(
    account_number: str,
    start_date: str | None = None,
    end_date: str | None = None,
    max_results: int = 50,
) -> str:
    """Get transaction history for a Fidelity account.

    Args:
        account_number: The account number (obtain from get_accounts).
        start_date: Optional start date in YYYY-MM-DD format.
        end_date: Optional end date in YYYY-MM-DD format.
        max_results: Maximum number of transactions to return (default 50).
    """
    try:
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
    except ValueError as e:
        return f"Error: Invalid date format — use YYYY-MM-DD. ({e})"

    try:
        txns = _get_client().get_transactions(account_number, start, end, max_results)
    except FidelityAPIError as e:
        return f"Error: {e}"

    if not txns:
        return f"No transactions found for account {account_number}."
    return json.dumps([t.model_dump() for t in txns], indent=2)


# ------------------------------------------------------------------
# Quote tool
# ------------------------------------------------------------------


@mcp.tool()
def get_quote(symbol: str) -> str:
    """Get a real-time market quote for a stock or ETF symbol.

    Args:
        symbol: Ticker symbol, e.g. AAPL, MSFT, VOO.
    """
    try:
        quote = _get_client().get_quote(symbol)
    except FidelityAPIError as e:
        return f"Error: {e}"
    return json.dumps(quote.model_dump(), indent=2)


# ------------------------------------------------------------------
# Trading tools
# ------------------------------------------------------------------


@mcp.tool()
def preview_trade(
    account_number: str,
    symbol: str,
    action: str,
    quantity: float,
    order_type: str = "MARKET",
    limit_price: float | None = None,
    duration: str = "DAY",
) -> str:
    """Preview a trade to see estimated cost, commission, and any warnings.

    Always call this before place_trade and show the result to the user.

    Args:
        account_number: Account to trade in (from get_accounts).
        symbol: Ticker symbol, e.g. AAPL.
        action: BUY or SELL.
        quantity: Number of shares.
        order_type: MARKET (default) or LIMIT.
        limit_price: Required when order_type is LIMIT.
        duration: DAY (default) or GTC (good-till-cancelled).
    """
    action = action.upper()
    if action not in ("BUY", "SELL"):
        return "Error: action must be BUY or SELL"
    if order_type.upper() == "LIMIT" and limit_price is None:
        return "Error: limit_price is required for LIMIT orders"

    try:
        preview = _get_client().preview_trade(
            account_number, symbol, action, quantity, order_type, limit_price, duration
        )
    except FidelityAPIError as e:
        return f"Error: {e}"

    return json.dumps(preview.model_dump(), indent=2)


@mcp.tool()
def place_trade(
    account_number: str,
    symbol: str,
    action: str,
    quantity: float,
    order_type: str = "MARKET",
    limit_price: float | None = None,
    duration: str = "DAY",
    confirm: bool = False,
) -> str:
    """Submit a real trade order on Fidelity. THIS EXECUTES A REAL TRADE.

    You MUST call preview_trade first and present the result to the user.
    Only call this tool after the user has explicitly confirmed they want to proceed.

    Args:
        account_number: Account to trade in (from get_accounts).
        symbol: Ticker symbol, e.g. AAPL.
        action: BUY or SELL.
        quantity: Number of shares.
        order_type: MARKET (default) or LIMIT.
        limit_price: Required when order_type is LIMIT.
        duration: DAY (default) or GTC (good-till-cancelled).
        confirm: Must be True — acts as an explicit confirmation gate.
    """
    if not confirm:
        return (
            "Trade not submitted. Set confirm=True only after presenting the "
            "preview_trade result to the user and receiving explicit approval."
        )

    action = action.upper()
    if action not in ("BUY", "SELL"):
        return "Error: action must be BUY or SELL"
    if order_type.upper() == "LIMIT" and limit_price is None:
        return "Error: limit_price is required for LIMIT orders"

    try:
        result = _get_client().place_trade(
            account_number, symbol, action, quantity, order_type, limit_price, duration
        )
    except FidelityAPIError as e:
        return f"Error: {e}"

    return json.dumps(result.model_dump(), indent=2)


def main() -> None:
    mcp.run()

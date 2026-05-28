"""Pydantic models for Fidelity API responses."""

from typing import Optional
from pydantic import BaseModel, Field


class AccountBalance(BaseModel):
    total_account_value: float
    today_gain_loss: float = 0.0
    today_gain_loss_pct: float = 0.0
    available_to_trade: Optional[float] = None
    available_to_withdraw: Optional[float] = None


class Account(BaseModel):
    account_number: str
    account_name: str
    account_type: str  # BROKERAGE, IRA, ROTH_IRA, 401K, etc.
    balance: AccountBalance


class Position(BaseModel):
    symbol: str
    description: str
    quantity: float
    last_price: float
    market_value: float
    cost_basis_per_share: Optional[float] = None
    cost_basis_total: Optional[float] = None
    total_gain_loss: Optional[float] = None
    total_gain_loss_pct: Optional[float] = None
    today_gain_loss: Optional[float] = None
    asset_class: Optional[str] = None  # EQUITY, ETF, MUTUAL_FUND, FIXED_INCOME


class Transaction(BaseModel):
    date: str
    settlement_date: Optional[str] = None
    action: str  # BUY, SELL, DIVIDEND, INTEREST, etc.
    symbol: Optional[str] = None
    description: str
    quantity: Optional[float] = None
    price: Optional[float] = None
    amount: float


class Quote(BaseModel):
    symbol: str
    last_price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    day_change: Optional[float] = None
    day_change_pct: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None


class OrderPreview(BaseModel):
    account_number: str
    symbol: str
    action: str  # BUY or SELL
    quantity: float
    order_type: str  # MARKET or LIMIT
    limit_price: Optional[float] = None
    duration: str  # DAY or GTC
    estimated_value: float
    estimated_commission: float
    estimated_total: float
    warnings: list[str] = Field(default_factory=list)


class OrderResult(BaseModel):
    order_number: str
    status: str
    account_number: str
    symbol: str
    action: str
    quantity: float
    message: str

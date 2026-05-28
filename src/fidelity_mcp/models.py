"""Pydantic models for Fidelity API responses."""


from pydantic import BaseModel, Field


class AccountBalance(BaseModel):
    total_account_value: float
    today_gain_loss: float = 0.0
    today_gain_loss_pct: float = 0.0
    available_to_trade: float | None = None
    available_to_withdraw: float | None = None


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
    cost_basis_per_share: float | None = None
    cost_basis_total: float | None = None
    total_gain_loss: float | None = None
    total_gain_loss_pct: float | None = None
    today_gain_loss: float | None = None
    asset_class: str | None = None  # EQUITY, ETF, MUTUAL_FUND, FIXED_INCOME


class Transaction(BaseModel):
    date: str
    settlement_date: str | None = None
    action: str  # BUY, SELL, DIVIDEND, INTEREST, etc.
    symbol: str | None = None
    description: str
    quantity: float | None = None
    price: float | None = None
    amount: float


class Quote(BaseModel):
    symbol: str
    last_price: float
    bid: float | None = None
    ask: float | None = None
    volume: int | None = None
    day_high: float | None = None
    day_low: float | None = None
    day_change: float | None = None
    day_change_pct: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None


class OrderPreview(BaseModel):
    account_number: str
    symbol: str
    action: str  # BUY or SELL
    quantity: float
    order_type: str  # MARKET or LIMIT
    limit_price: float | None = None
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

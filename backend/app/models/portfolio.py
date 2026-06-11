from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

AccountType = Literal["Trading", "Investing", "Bank Account", "Overall"]
ActionType = Literal["Trade", "Deposit", "Withdraw"]
DirectionType = Literal["Long", "Short"]


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    starting_balance: float = Field(ge=0)
    type: AccountType

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class AccountResponse(AccountCreate):
    created_at: datetime | None = None


class TradeCreate(BaseModel):
    account: str
    trade_time: date
    action: ActionType
    type: DirectionType | None = None
    symbol: str = "CASH"
    pnl: float
    notes: str = ""

    @field_validator("account", "symbol")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


class TradeUpdate(BaseModel):
    trade_time: date
    action: ActionType
    type: DirectionType | None = None
    symbol: str = "CASH"
    pnl: float
    notes: str = ""


class TradeResponse(BaseModel):
    id: str
    account: str
    trade_time: datetime
    action: str
    type: str | None = None
    symbol: str
    pnl: float
    notes: str = ""


class AssetCreate(BaseModel):
    account: str
    symbol: str
    quantity: float = Field(gt=0)
    unit: str = "units"
    display_quantity: float | None = None

    @field_validator("account", "symbol")
    @classmethod
    def clean_asset_text(cls, value: str) -> str:
        return value.strip()


class AssetResponse(BaseModel):
    id: str
    account: str
    symbol: str
    quantity: float
    unit: str
    display_quantity: float
    created_at: datetime | None = None


class EquityPoint(BaseModel):
    date: datetime
    balance: float


class DashboardSummary(BaseModel):
    balance: float
    realised_pnl: float
    trade_count: int
    winning_trades: int
    win_rate: float
    average_trade: float
    best_trade: float
    equity_curve: list[EquityPoint]


class JournalSummary(BaseModel):
    total_entries: int
    trade_count: int
    realised_pnl: float
    win_rate: float
    average_trade: float

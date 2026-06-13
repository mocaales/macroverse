from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

AccountType = Literal["Savings", "Bank Account", "Trading Account"]
CurrencyCode = Literal["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD"]
ActionType = Literal["Trade", "Deposit", "Withdraw"]
DirectionType = Literal["Long", "Short"]
TransactionCategory = Literal[
    "Salary",
    "Groceries",
    "Food & Dining",
    "Rent & Housing",
    "Utilities",
    "Transport",
    "Health",
    "Gifts",
    "Entertainment",
    "Shopping",
    "Education",
    "Travel",
    "Transfer",
    "Savings",
    "Fees",
    "Other",
]


def normalize_account_type(value: str) -> str:
    legacy_types = {
        "Trading": "Trading Account",
        "Investing": "Trading Account",
    }
    return legacy_types.get(value, value)


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    starting_balance: float = Field(ge=0)
    type: AccountType
    currency: CurrencyCode = "EUR"

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_type(cls, data):
        if isinstance(data, dict) and "type" in data:
            return {**data, "type": normalize_account_type(data["type"])}
        return data

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Account name is required.")
        return cleaned


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
    description: str = ""
    category: TransactionCategory | None = None

    @field_validator("account", "symbol", "description")
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
    description: str = ""
    category: TransactionCategory | None = None


class TradeResponse(BaseModel):
    id: str
    account: str
    trade_time: datetime
    action: str
    type: str | None = None
    symbol: str
    pnl: float
    notes: str = ""
    description: str = ""
    category: TransactionCategory | None = None
    recurring_schedule_id: str | None = None


class RecurringTransactionCreate(BaseModel):
    account: str = Field(min_length=1, max_length=100)
    action: Literal["Deposit", "Withdraw"]
    amount: float = Field(gt=0)
    description: str = Field(min_length=1, max_length=200)
    category: TransactionCategory
    day_of_month: int = Field(ge=1, le=31)
    start_date: date
    end_date: date | None = None

    @field_validator("account", "description")
    @classmethod
    def clean_recurring_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field is required.")
        return cleaned

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("End date must be on or after the start date.")
        return self


class RecurringTransactionResponse(RecurringTransactionCreate):
    id: str
    active: bool = True
    created_at: datetime | None = None


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


class AccountBalance(BaseModel):
    name: str
    type: AccountType
    currency: CurrencyCode
    balance: float


class DashboardSummary(BaseModel):
    currency: CurrencyCode = "EUR"
    account_type: AccountType | Literal["All Accounts"] = "All Accounts"
    account_count: int = 0
    balance: float
    realised_pnl: float
    total_entries: int = 0
    trade_count: int
    winning_trades: int
    win_rate: float
    average_trade: float
    best_trade: float
    equity_curve: list[EquityPoint]
    accounts: list[AccountBalance] = Field(default_factory=list)


class JournalSummary(BaseModel):
    total_entries: int
    trade_count: int
    realised_pnl: float
    win_rate: float
    average_trade: float

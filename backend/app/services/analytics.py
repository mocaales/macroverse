from datetime import UTC, date, datetime, time, timedelta


def _day_start(value: date | datetime) -> datetime:
    day = value.date() if isinstance(value, datetime) else value
    return datetime.combine(day, time.min, tzinfo=UTC)


def _daily_range(start: datetime, end: datetime):
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def _balance_curve(events: list[tuple[date | datetime, float]], through: datetime | None = None) -> list[dict]:
    if not events:
        return []
    balance = 0.0
    daily_amounts: dict[datetime, float] = {}
    for event_date, amount in sorted(events, key=lambda item: item[0]):
        day = _day_start(event_date)
        daily_amounts[day] = daily_amounts.get(day, 0.0) + amount
    first_day = min(daily_amounts)
    last_day = max(_day_start(through or datetime.now(UTC)), max(daily_amounts))
    curve = []
    for event_day in _daily_range(first_day, last_day):
        balance += daily_amounts.get(event_day, 0.0)
        curve.append({"date": event_day, "balance": balance})
    return curve


def _daily_pnl(trades: list[dict], through: datetime | None = None) -> list[dict]:
    trade_days: dict[datetime, dict[str, float | int]] = {}
    closed = [trade for trade in trades if trade.get("action") == "Trade"]
    if not closed:
        return []
    for trade in closed:
        day = _day_start(trade["trade_time"])
        current = trade_days.setdefault(day, {"pnl": 0.0, "trade_count": 0})
        current["pnl"] = float(current["pnl"]) + float(trade["pnl"])
        current["trade_count"] = int(current["trade_count"]) + 1
    first_day = min(trade_days)
    last_day = max(_day_start(through or datetime.now(UTC)), max(trade_days))
    return [
        {
            "date": event_day,
            "pnl": float(trade_days.get(event_day, {}).get("pnl", 0)),
            "trade_count": int(trade_days.get(event_day, {}).get("trade_count", 0)),
        }
        for event_day in _daily_range(first_day, last_day)
    ]


def dashboard_summary(account: dict, trades: list[dict]) -> dict:
    starting_balance = float(account.get("starting_balance", 0))
    ordered = sorted(trades, key=lambda item: item["trade_time"])
    created_at = account.get("created_at") or (ordered[0]["trade_time"] if ordered else datetime.now(UTC))
    if ordered:
        created_at = min(created_at, ordered[0]["trade_time"] - timedelta(microseconds=1))
    events = [(created_at, starting_balance)]
    events.extend((trade["trade_time"], float(trade["pnl"])) for trade in ordered)
    curve = _balance_curve(events)
    balance = curve[-1]["balance"] if curve else starting_balance

    closed = [trade for trade in trades if trade.get("action") == "Trade"]
    wins = [trade for trade in closed if float(trade["pnl"]) > 0]
    pnl = sum(float(trade["pnl"]) for trade in trades)
    trade_pnls = [float(trade["pnl"]) for trade in closed]
    return {
        "currency": account.get("currency", "USD"),
        "account_type": account.get("type", "Trading Account"),
        "account_count": 1,
        "balance": balance,
        "realised_pnl": pnl,
        "total_entries": len(trades),
        "trade_count": len(closed),
        "winning_trades": len(wins),
        "win_rate": (len(wins) / len(closed) * 100) if closed else 0,
        "average_trade": (sum(trade_pnls) / len(trade_pnls)) if trade_pnls else 0,
        "best_trade": max(trade_pnls, default=0),
        "equity_curve": curve,
        "daily_pnl": _daily_pnl(ordered),
        "accounts": [],
    }


def aggregate_dashboard_summary(accounts: list[dict], trades: list[dict], currency: str) -> dict:
    selected = [account for account in accounts if account.get("currency", "USD") == currency]
    names = {account["name"] for account in selected}
    events = []
    for account in selected:
        created_at = account.get("created_at") or datetime.now(UTC)
        account_trades = [trade for trade in trades if trade.get("account") == account["name"]]
        if account_trades:
            first_trade_at = min(trade["trade_time"] for trade in account_trades)
            created_at = min(created_at, first_trade_at - timedelta(microseconds=1))
        events.append((created_at, float(account.get("starting_balance", 0))))
    selected_trades = [trade for trade in trades if trade.get("account") in names]
    events.extend((trade["trade_time"], float(trade["pnl"])) for trade in selected_trades)
    curve = _balance_curve(events)
    balance = curve[-1]["balance"] if curve else 0.0

    closed = [trade for trade in selected_trades if trade.get("action") == "Trade"]
    trade_pnls = [float(trade["pnl"]) for trade in closed]
    wins = [value for value in trade_pnls if value > 0]
    account_balances = []
    for account in selected:
        account_trades = [trade for trade in selected_trades if trade.get("account") == account["name"]]
        account_balances.append(
            {
                "name": account["name"],
                "type": account.get("type", "Trading Account"),
                "currency": currency,
                "balance": float(account.get("starting_balance", 0))
                + sum(float(trade["pnl"]) for trade in account_trades),
            }
        )
    return {
        "currency": currency,
        "account_type": "All Accounts",
        "account_count": len(selected),
        "balance": balance,
        "realised_pnl": sum(float(trade["pnl"]) for trade in selected_trades),
        "total_entries": len(selected_trades),
        "trade_count": len(closed),
        "winning_trades": len(wins),
        "win_rate": (len(wins) / len(closed) * 100) if closed else 0,
        "average_trade": (sum(trade_pnls) / len(trade_pnls)) if trade_pnls else 0,
        "best_trade": max(trade_pnls, default=0),
        "equity_curve": curve,
        "daily_pnl": _daily_pnl(selected_trades),
        "accounts": account_balances,
    }


def journal_summary(trades: list[dict]) -> dict:
    closed = [trade for trade in trades if trade.get("action") == "Trade"]
    trade_pnls = [float(trade["pnl"]) for trade in closed]
    wins = [value for value in trade_pnls if value > 0]
    return {
        "total_entries": len(trades),
        "trade_count": len(closed),
        "realised_pnl": sum(float(trade["pnl"]) for trade in trades),
        "win_rate": (len(wins) / len(closed) * 100) if closed else 0,
        "average_trade": (sum(trade_pnls) / len(trade_pnls)) if trade_pnls else 0,
    }

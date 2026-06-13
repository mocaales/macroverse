from datetime import UTC, date, datetime, time, timedelta


def _day_start(value: date | datetime) -> datetime:
    day = value.date() if isinstance(value, datetime) else value
    return datetime.combine(day, time.min, tzinfo=UTC)


def _balance_curve(events: list[tuple[date | datetime, float]]) -> list[dict]:
    balance = 0.0
    daily_balances: dict[datetime, float] = {}
    for event_date, amount in sorted(events, key=lambda item: item[0]):
        balance += amount
        daily_balances[_day_start(event_date)] = balance
    return [
        {"date": event_date, "balance": daily_balances[event_date]}
        for event_date in sorted(daily_balances)
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

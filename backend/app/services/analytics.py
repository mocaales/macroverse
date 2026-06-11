from datetime import UTC, datetime


def dashboard_summary(account: dict, trades: list[dict]) -> dict:
    starting_balance = float(account.get("starting_balance", 0))
    ordered = sorted(trades, key=lambda item: item["trade_time"])
    balance = starting_balance
    curve = []
    created_at = account.get("created_at") or (ordered[0]["trade_time"] if ordered else datetime.now(UTC))
    curve.append({"date": created_at, "balance": starting_balance})
    for trade in ordered:
        balance += float(trade["pnl"])
        curve.append({"date": trade["trade_time"], "balance": balance})

    closed = [trade for trade in trades if trade.get("action") == "Trade"]
    wins = [trade for trade in closed if float(trade["pnl"]) > 0]
    pnl = sum(float(trade["pnl"]) for trade in trades)
    trade_pnls = [float(trade["pnl"]) for trade in closed]
    return {
        "balance": balance,
        "realised_pnl": pnl,
        "trade_count": len(closed),
        "winning_trades": len(wins),
        "win_rate": (len(wins) / len(closed) * 100) if closed else 0,
        "average_trade": (sum(trade_pnls) / len(trade_pnls)) if trade_pnls else 0,
        "best_trade": max(trade_pnls, default=0),
        "equity_curve": curve,
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

from datetime import UTC, datetime

from app.models.portfolio import TradeResponse
from app.services.analytics import dashboard_summary, journal_summary


def test_dashboard_summary_preserves_balance_and_trade_metrics():
    account = {"starting_balance": 1000, "created_at": datetime(2026, 1, 1, tzinfo=UTC)}
    trades = [
        {"trade_time": datetime(2026, 1, 2, tzinfo=UTC), "action": "Trade", "pnl": 100},
        {"trade_time": datetime(2026, 1, 3, tzinfo=UTC), "action": "Trade", "pnl": -40},
        {"trade_time": datetime(2026, 1, 4, tzinfo=UTC), "action": "Deposit", "pnl": 500},
    ]

    summary = dashboard_summary(account, trades)

    assert summary["balance"] == 1560
    assert summary["realised_pnl"] == 560
    assert summary["trade_count"] == 2
    assert summary["winning_trades"] == 1
    assert summary["win_rate"] == 50
    assert summary["average_trade"] == 30
    assert len(summary["equity_curve"]) == 4


def test_journal_summary_uses_trades_for_win_rate():
    trades = [
        {"action": "Trade", "pnl": 50},
        {"action": "Trade", "pnl": -10},
        {"action": "Withdraw", "pnl": -100},
    ]

    summary = journal_summary(trades)

    assert summary == {
        "total_entries": 3,
        "trade_count": 2,
        "realised_pnl": -60,
        "win_rate": 50,
        "average_trade": 20,
    }


def test_cash_entry_response_allows_empty_trade_direction():
    response = TradeResponse.model_validate(
        {
            "id": "entry-1",
            "account": "Main",
            "trade_time": datetime(2026, 6, 11, tzinfo=UTC),
            "action": "Deposit",
            "type": None,
            "symbol": "CASH",
            "pnl": 100,
            "notes": "",
        }
    )

    assert response.type is None

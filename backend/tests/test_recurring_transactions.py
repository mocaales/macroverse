from datetime import date, datetime

from app.services.recurring_transactions import scheduled_occurrences, sync_recurring_transactions


def test_scheduled_occurrences_support_month_end_and_date_limits():
    assert scheduled_occurrences(date(2026, 1, 31), 31, date(2026, 3, 31)) == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]
    assert scheduled_occurrences(date(2026, 7, 1), 1, date(2026, 6, 1)) == []
    assert scheduled_occurrences(date(2026, 1, 1), 1, date(2026, 4, 1), date(2026, 2, 15)) == [
        date(2026, 1, 1),
        date(2026, 2, 1),
    ]


class Repository:
    def __init__(self):
        self.created = []
        self.identifiers = set()

    def list_recurring_transactions(self, _uid):
        return [
            {
                "id": "salary",
                "account": "Current",
                "action": "Deposit",
                "amount": 100,
                "description": "Salary",
                "category": "Salary",
                "day_of_month": 1,
                "start_date": datetime(2026, 1, 1),
                "end_date": None,
                "active": True,
            },
            {
                "id": "inactive",
                "account": "Current",
                "action": "Withdraw",
                "amount": 10,
                "description": "Old fee",
                "category": "Fees",
                "day_of_month": 1,
                "start_date": date(2026, 1, 1),
                "active": False,
            },
        ]

    def create_recurring_trade(self, _uid, identifier, payload):
        if identifier in self.identifiers:
            return None
        self.identifiers.add(identifier)
        self.created.append((identifier, payload))
        return payload


def test_sync_materializes_due_transactions_once():
    repository = Repository()

    assert sync_recurring_transactions(repository, "u1", date(2026, 3, 15)) == 3
    assert sync_recurring_transactions(repository, "u1", date(2026, 3, 15)) == 0
    assert len(repository.created) == 3
    assert repository.created[0][1]["pnl"] == 100
    assert repository.created[0][1]["recurring_schedule_id"] == "salary"

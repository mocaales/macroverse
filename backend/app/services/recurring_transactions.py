import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.repositories.portfolio import PortfolioRepository


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def scheduled_occurrences(
    start_date: date,
    day_of_month: int,
    through_date: date,
    end_date: date | None = None,
) -> list[date]:
    if start_date > through_date:
        return []

    year, month = start_date.year, start_date.month
    occurrences = []
    while date(year, month, 1) <= through_date:
        last_day = calendar.monthrange(year, month)[1]
        occurrence = date(year, month, min(day_of_month, last_day))
        if occurrence >= start_date and occurrence <= through_date and (end_date is None or occurrence <= end_date):
            occurrences.append(occurrence)
        if end_date and date(year, month, 1) > end_date:
            break
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return occurrences


def sync_recurring_transactions(
    repository: PortfolioRepository,
    uid: str,
    today: date | None = None,
) -> int:
    through_date = today or datetime.now(ZoneInfo(get_settings().app_timezone)).date()
    created = 0
    for schedule in repository.list_recurring_transactions(uid) or []:
        if not schedule.get("active", True):
            continue
        start_date = _as_date(schedule["start_date"])
        end_value = schedule.get("end_date")
        end_date = _as_date(end_value) if end_value else None
        for occurrence in scheduled_occurrences(
            start_date,
            int(schedule["day_of_month"]),
            through_date,
            end_date,
        ):
            schedule_id = schedule["id"]
            identifier = f"recurring-{schedule_id}-{occurrence.isoformat()}"
            amount = abs(float(schedule["amount"]))
            payload = {
                "account": schedule["account"],
                "trade_time": occurrence,
                "action": schedule["action"],
                "type": None,
                "symbol": "CASH",
                "pnl": -amount if schedule["action"] == "Withdraw" else amount,
                "notes": "",
                "description": schedule["description"],
                "category": schedule["category"],
                "recurring_schedule_id": schedule_id,
            }
            if repository.create_recurring_trade(uid, identifier, payload):
                created += 1
    return created

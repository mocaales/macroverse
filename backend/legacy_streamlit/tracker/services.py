import calendar
from datetime import datetime, date

import pandas as pd


def get_accounts(db, user_email):
    if not user_email:
        return []
    accounts = list(
        db.accounts.find(
            {"user": user_email},
            {
                "_id": 0,
                "name": 1,
                "starting_balance": 1,
                "created_at": 1,
                "type": 1,
            },
        )
    )
    return sorted(accounts, key=lambda x: x["name"].lower())

def get_account(db, user_email, name):
    if not user_email:
        return None
    return db.accounts.find_one({"user": user_email, "name": name}, {"_id": 0})


def upsert_account(db, user_email, name, starting_balance, account_type):
    if not user_email:
        return
    db.accounts.update_one(
        {"user": user_email, "name": name},
        {
            "$set": {
                "user": user_email,
                "name": name,
                "starting_balance": starting_balance,
                "type": account_type,
            },
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )


def add_asset(db, asset, user_email):
    if not user_email:
        return
    payload = dict(asset)
    payload["user"] = user_email
    db.investments.insert_one(payload)


def load_assets(db, account, user_email):
    if not user_email:
        return pd.DataFrame()
    cursor = db.investments.find({"account": account, "user": user_email})
    rows = list(cursor)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df


def add_trade(db, trade, user_email):
    if not user_email:
        return
    payload = dict(trade)
    payload["user"] = user_email
    db.trades.insert_one(payload)


def load_trades(db, accounts, user_email):
    if not accounts or not user_email:
        return pd.DataFrame()
    cursor = db.trades.find({"account": {"$in": accounts}, "user": user_email})
    rows = list(cursor)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["trade_time"] = pd.to_datetime(df["trade_time"])
    return df.sort_values("trade_time")


def equity_curve(trades_df, accounts_map, accounts_created):
    if trades_df.empty:
        return pd.DataFrame()
    trades_df = trades_df.copy()
    trades_df["trade_time"] = pd.to_datetime(trades_df["trade_time"], utc=True, errors="coerce")
    curves = []
    for account, group in trades_df.groupby("account"):
        group = group.sort_values("trade_time").copy()
        start = accounts_map.get(account, 0.0)
        group["cumulative_pnl"] = group["pnl"].cumsum()
        group["balance"] = start + group["cumulative_pnl"]
        curve = group[["trade_time", "balance"]].copy()
        curve["account"] = account

        start_date = accounts_created.get(account) or curve["trade_time"].iloc[0]
        start_date = pd.to_datetime(start_date, utc=True, errors="coerce")
        deposit_date = start_date + pd.Timedelta(minutes=1)
        start_rows = pd.DataFrame(
            [
                {"trade_time": start_date, "balance": 0.0, "account": account},
                {"trade_time": deposit_date, "balance": start, "account": account},
            ]
        )
        curve = pd.concat([start_rows, curve], ignore_index=True).sort_values("trade_time")

        daily = curve.set_index("trade_time").sort_index()
        daily = daily.groupby(level=0).last()
        idx = pd.date_range(daily.index.min().normalize(), daily.index.max().normalize(), freq="D")
        daily = daily.reindex(idx, method="ffill")
        daily = daily.reset_index().rename(columns={"index": "trade_time"})
        daily["account"] = account
        curves.append(daily)
    return pd.concat(curves, ignore_index=True)


def daily_pnl_calendar(trades_df, month_date):
    if trades_df.empty:
        return pd.DataFrame()
    df = trades_df.copy()
    df["day"] = df["trade_time"].dt.date
    daily = df.groupby("day", as_index=False)["pnl"].sum()
    daily["month"] = pd.to_datetime(daily["day"]).dt.to_period("M")
    target_month = pd.Period(month_date, freq="M")
    return daily[daily["month"] == target_month]


def month_weeks(month_pick):
    cal = calendar.Calendar(firstweekday=6)
    return cal.monthdayscalendar(month_pick.year, month_pick.month)


def month_range(trades_df):
    min_dt = trades_df["trade_time"].min().date()
    max_dt = trades_df["trade_time"].max().date()
    months = pd.period_range(
        start=pd.Period(min_dt, freq="M"),
        end=pd.Period(max_dt, freq="M"),
        freq="M",
    )
    labels = [m.strftime("%Y-%m") for m in months]
    return labels, min_dt, max_dt


def parse_month_label(label):
    return date(int(label[:4]), int(label[5:7]), 1)


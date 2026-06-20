import { useMemo, useState } from "react";
import type { CurrencyCode, DashboardSummary } from "../types";

type DailyPnlPoint = DashboardSummary["daily_pnl"][number];

interface DailyPnlCalendarProps {
  readonly currency: CurrencyCode;
  readonly points: DailyPnlPoint[];
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

type CalendarBlank = { key: string };
type CalendarDay = { date: Date; key: string };

function utcDateKey(value: string) {
  const date = new Date(value);
  return date.toISOString().slice(0, 10);
}

function monthKey(value: string) {
  return utcDateKey(value).slice(0, 7);
}

function monthLabel(value: string) {
  return new Intl.DateTimeFormat("en-US", { month: "long", timeZone: "UTC", year: "numeric" })
    .format(new Date(`${value}-01T00:00:00Z`));
}

function dayNumber(value: Date) {
  return value.getUTCDate();
}

function pnlTone(value: number) {
  if (value > 0) return "gain";
  if (value < 0) return "loss";
  return "flat";
}

function formatMoney(value: number, currency: CurrencyCode, sign = false) {
  const formatted = new Intl.NumberFormat("en-US", {
    currency,
    maximumFractionDigits: Math.abs(value) >= 1_000 ? 0 : 2,
    style: "currency"
  }).format(Math.abs(value));
  if (!sign || value === 0) return formatted;
  return `${value > 0 ? "+" : "-"}${formatted}`;
}

function buildMonthDays(selectedMonth: string): Array<CalendarBlank | CalendarDay> {
  const first = new Date(`${selectedMonth}-01T00:00:00Z`);
  const daysInMonth = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
  const leadingBlanks = first.getUTCDay();
  const blanks = Array.from({ length: leadingBlanks }, (_, index) => ({ key: `blank-${index}` }));
  const days = Array.from({ length: daysInMonth }, (_, index) => {
    const day = index + 1;
    const date = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), day));
    return {
      date,
      key: date.toISOString().slice(0, 10)
    };
  });
  return [...blanks, ...days];
}

export function DailyPnlCalendar({ currency, points }: DailyPnlCalendarProps) {
  const pointsByDate = useMemo(
    () => new Map(points.map((point) => [utcDateKey(point.date), point])),
    [points]
  );
  const months = useMemo(() => {
    const uniqueMonths = [...new Set(points.map((point) => monthKey(point.date)))]
      .sort((left, right) => left.localeCompare(right));
    return uniqueMonths.length ? uniqueMonths : [new Date().toISOString().slice(0, 7)];
  }, [points]);
  const [selectedMonth, setSelectedMonth] = useState(months.at(-1) || new Date().toISOString().slice(0, 7));
  const monthDays = buildMonthDays(selectedMonth);
  const monthPoints = points.filter((point) => monthKey(point.date) === selectedMonth);
  const totalPnl = monthPoints.reduce((sum, point) => sum + point.pnl, 0);
  const winningDays = monthPoints.filter((point) => point.pnl > 0).length;
  const losingDays = monthPoints.filter((point) => point.pnl < 0).length;
  const breakEvenDays = monthPoints.filter((point) => point.pnl === 0).length;

  return (
    <section className="panel daily-pnl-panel">
      <div className="daily-pnl-calendar">
        <div className="daily-pnl-main">
          <div className="daily-pnl-heading">
            <div>
              <p className="eyebrow">Daily P&L</p>
              <h2>Trading calendar</h2>
            </div>
            <select
              aria-label="P&L month"
              value={selectedMonth}
              onChange={(event) => setSelectedMonth(event.target.value)}
            >
              {months.map((item) => <option key={item} value={item}>{monthLabel(item)}</option>)}
            </select>
            <div className="pnl-legend">
              <span><i className="gain" /> Gain</span>
              <span><i className="loss" /> Loss</span>
            </div>
          </div>
          <div className="calendar-weekdays">
            {WEEKDAYS.map((weekday) => <span key={weekday}>{weekday}</span>)}
          </div>
          <div className="calendar-grid">
            {monthDays.map((item) => {
              const calendarDay = "date" in item ? item : null;
              if (!calendarDay) return <span aria-hidden="true" className="calendar-day empty" key={item.key} />;
              const pnlPoint = pointsByDate.get(calendarDay.key);
              const pnl = pnlPoint?.pnl || 0;
              const tone = pnlTone(pnl);
              return (
                <span className={`calendar-day ${tone}`} key={calendarDay.key}>
                  <strong>{dayNumber(calendarDay.date)}</strong>
                  <em>{pnl === 0 ? "0.00" : formatMoney(pnl, currency, true)}</em>
                  {Boolean(pnlPoint?.trade_count) && <small>{pnlPoint?.trade_count} trade{pnlPoint?.trade_count === 1 ? "" : "s"}</small>}
                </span>
              );
            })}
          </div>
        </div>
        <aside className="daily-pnl-analysis">
          <h2>P&L analysis</h2>
          <dl>
            <div>
              <dt>Total P&L</dt>
              <dd className={totalPnl >= 0 ? "positive" : "negative"}>{formatMoney(totalPnl, currency, true)}</dd>
            </div>
            <div><dt>Winning days</dt><dd>{winningDays}</dd></div>
            <div><dt>Losing days</dt><dd>{losingDays}</dd></div>
            <div><dt>Break-even days</dt><dd>{breakEvenDays}</dd></div>
          </dl>
        </aside>
      </div>
    </section>
  );
}

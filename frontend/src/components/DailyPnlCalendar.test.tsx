import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DailyPnlCalendar } from "./DailyPnlCalendar";

describe("DailyPnlCalendar", () => {
  it("renders gain and loss days with monthly analysis", () => {
    render(
      <DailyPnlCalendar
        currency="EUR"
        points={[
          { date: "2026-06-01T00:00:00Z", pnl: 100, trade_count: 2 },
          { date: "2026-06-02T00:00:00Z", pnl: -25, trade_count: 1 },
          { date: "2026-06-03T00:00:00Z", pnl: 0, trade_count: 0 },
          { date: "2026-07-01T00:00:00Z", pnl: 50, trade_count: 1 }
        ]}
      />
    );

    expect(screen.getByText("Trading calendar")).toBeInTheDocument();
    expect(screen.getAllByText("+€50.00")).toHaveLength(2);
    expect(screen.queryByText("Total P&L%")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("P&L month"), { target: { value: "2026-06" } });

    expect(screen.getByText("+€100.00")).toBeInTheDocument();
    expect(screen.getByText("-€25.00")).toBeInTheDocument();
    expect(screen.getByText("2 trades")).toBeInTheDocument();
  });

  it("renders the current month shell when no P&L exists", () => {
    render(<DailyPnlCalendar currency="USD" points={[]} />);

    expect(screen.getByText("Trading calendar")).toBeInTheDocument();
    expect(screen.getByText("$0.00")).toBeInTheDocument();
    expect(screen.queryByText("Total P&L%")).not.toBeInTheDocument();
  });
});

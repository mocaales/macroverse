import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccountSelector } from "../../components/AccountSelector";
import { CreateAccountForm } from "./CreateAccountForm";
import { RiskCalculator } from "./RiskCalculator";
import { TradeForm } from "./TradeForm";

describe("dashboard forms", () => {
  it("normalizes account input before creating an account", () => {
    const onCreate = vi.fn();
    render(<CreateAccountForm busy={false} onCreate={onCreate} />);

    fireEvent.change(screen.getByLabelText("Account name"), { target: { value: "  Long Term  " } });
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "CHF" } });
    expect(screen.queryByText("Account type")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Starting balance")).toHaveValue(null);
    expect(screen.getByLabelText("Starting balance")).toHaveAttribute("step", "0.01");
    fireEvent.change(screen.getByLabelText("Starting balance"), { target: { value: "2500.75" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(onCreate).toHaveBeenCalledWith({
      name: "Long Term",
      starting_balance: 2500.75,
      type: "Trading Account",
      currency: "CHF"
    });
    expect(screen.getByLabelText("Account name")).toHaveValue("");
    expect(screen.getByLabelText("Starting balance")).toHaveValue(null);
  });

  it("uses zero when starting balance is left empty", () => {
    const onCreate = vi.fn();
    render(<CreateAccountForm busy={false} onCreate={onCreate} />);

    fireEvent.change(screen.getByLabelText("Account name"), { target: { value: "Empty account" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ starting_balance: 0 }));
  });

  it("converts withdrawals into negative cash entries", () => {
    const onSubmit = vi.fn();
    render(<TradeForm account="Main" busy={false} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Action"), { target: { value: "Withdraw" } });
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "125" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit entry" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        account: "Main",
        action: "Withdraw",
        symbol: "CASH",
        pnl: -125,
        type: undefined
      })
    );
  });

  it("uses trade result to submit losses without manually typing a minus", () => {
    const onSubmit = vi.fn();
    render(<TradeForm account="Main" busy={false} onSubmit={onSubmit} />);

    expect(screen.getByLabelText("Realised P&L")).toHaveValue(null);
    fireEvent.change(screen.getByLabelText("Symbol"), { target: { value: "eth" } });
    fireEvent.change(screen.getByLabelText("Trade result"), { target: { value: "loss" } });
    fireEvent.change(screen.getByLabelText("Realised P&L"), { target: { value: "45.5" } });
    expect(screen.getByLabelText("Realised P&L")).toHaveValue(-45.5);
    fireEvent.click(screen.getByRole("button", { name: "Submit entry" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      action: "Trade",
      pnl: -45.5,
      symbol: "ETH"
    }));
    expect(screen.getByLabelText("Realised P&L")).toHaveValue(null);
  });

  it.each([
    { action: "Trade", expected: 20, result: "profit" },
    { action: "Trade", expected: 0, result: "flat" },
    { action: "Deposit", expected: 20, result: "profit" }
  ] as const)("submits $action entries with a $result result", ({ action, expected, result }) => {
    const onSubmit = vi.fn();
    render(<TradeForm account="Main" busy={false} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Action"), { target: { value: action } });
    if (action === "Trade") {
      fireEvent.change(screen.getByLabelText("Symbol"), { target: { value: "btc" } });
      fireEvent.change(screen.getByLabelText("Trade result"), { target: { value: result } });
    }
    fireEvent.change(screen.getByLabelText(action === "Trade" ? "Realised P&L" : "Amount"), {
      target: { value: "20" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit entry" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ action, pnl: expected }));
  });

  it("recalculates position sizing from user inputs", () => {
    const view = render(<RiskCalculator initialBalance={10_000} />);

    expect(screen.getByLabelText("Portfolio balance")).toHaveValue(10_000);
    expect(screen.getByLabelText("Portfolio balance")).toHaveAttribute("readonly");
    expect(screen.getByText("$1,666.67")).toBeInTheDocument();
    expect(screen.getByText("$5,000.00")).toBeInTheDocument();
    expect(screen.getByText("$100.00")).toBeInTheDocument();
    expect(screen.getByText("$200.00")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Risk %"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Stop %"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Leverage"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Reward ratio"), { target: { value: "3" } });

    expect(screen.getByText("$1,666.67")).toBeInTheDocument();
    expect(screen.getByText("$6,666.67")).toBeInTheDocument();
    expect(screen.getByText("$200.00")).toBeInTheDocument();
    expect(screen.getByText("$600.00")).toBeInTheDocument();

    view.rerender(<RiskCalculator initialBalance={12_000} />);
    expect(screen.getByLabelText("Portfolio balance")).toHaveValue(12_000);
    expect(screen.getByText("$2,000.00")).toBeInTheDocument();
    expect(screen.getByText("$8,000.00")).toBeInTheDocument();
    expect(screen.getByText("$240.00")).toBeInTheDocument();
    expect(screen.getByText("$720.00")).toBeInTheDocument();
  });

  it("reports account selection changes", () => {
    const onChange = vi.fn();
    render(
      <AccountSelector
        accounts={[
          {
            name: "Brokerage",
            starting_balance: 1000,
            type: "Trading Account",
            currency: "USD",
            created_at: "2026-06-11T00:00:00Z"
          }
        ]}
        value=""
        onChange={onChange}
      />
    );

    fireEvent.change(screen.getByLabelText("Account"), { target: { value: "Brokerage" } });

    expect(onChange).toHaveBeenCalledWith("Brokerage");
  });
});

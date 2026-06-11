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
    fireEvent.change(screen.getByLabelText("Account type"), { target: { value: "Investing" } });
    fireEvent.change(screen.getByLabelText("Starting balance"), { target: { value: "2500" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(onCreate).toHaveBeenCalledWith({
      name: "Long Term",
      starting_balance: 2500,
      type: "Investing"
    });
    expect(screen.getByLabelText("Account name")).toHaveValue("");
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

  it("recalculates position sizing from user inputs", () => {
    render(<RiskCalculator initialBalance={10_000} />);

    expect(screen.getByText("$1,666.67")).toBeInTheDocument();
    expect(screen.getByText("$5,000.00")).toBeInTheDocument();
    expect(screen.getByText("$100.00")).toBeInTheDocument();
    expect(screen.getByText("$200.00")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Risk %"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Portfolio"), { target: { value: "12000" } });
    fireEvent.change(screen.getByLabelText("Stop %"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Leverage"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Reward ratio"), { target: { value: "3" } });

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
            type: "Trading",
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

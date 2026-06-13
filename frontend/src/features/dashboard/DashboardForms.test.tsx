import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccountSelector } from "../../components/AccountSelector";
import { CashTransactionForm } from "./CashTransactionForm";
import { CreateAccountForm } from "./CreateAccountForm";
import { RecurringTransactionsPanel } from "./RecurringTransactionsPanel";
import { RiskCalculator } from "./RiskCalculator";
import { TradeForm } from "./TradeForm";

describe("dashboard forms", () => {
  it("normalizes account input before creating an account", () => {
    const onCreate = vi.fn();
    render(<CreateAccountForm busy={false} onCreate={onCreate} />);

    fireEvent.change(screen.getByLabelText("Account name"), { target: { value: "  Long Term  " } });
    fireEvent.change(screen.getByLabelText("Account type"), { target: { value: "Savings" } });
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "CHF" } });
    expect(screen.getByLabelText("Starting balance")).toHaveValue(null);
    expect(screen.getByLabelText("Starting balance")).toHaveAttribute("step", "0.01");
    fireEvent.change(screen.getByLabelText("Starting balance"), { target: { value: "2500.75" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(onCreate).toHaveBeenCalledWith({
      name: "Long Term",
      starting_balance: 2500.75,
      type: "Savings",
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

  it("creates categorized bank transactions and savings deposits", () => {
    const bankSubmit = vi.fn();
    const view = render(
      <CashTransactionForm
        account="Current"
        accountType="Bank Account"
        busy={false}
        currency="EUR"
        onSubmit={bankSubmit}
      />
    );
    fireEvent.change(screen.getByLabelText("Transaction"), { target: { value: "Withdraw" } });
    fireEvent.change(screen.getByLabelText("Amount (EUR)"), { target: { value: "45" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Weekly groceries" } });
    fireEvent.click(screen.getByRole("button", { name: "Groceries" }));
    fireEvent.click(screen.getByRole("button", { name: "Add transaction" }));
    expect(bankSubmit).toHaveBeenCalledWith(expect.objectContaining({
      action: "Withdraw",
      category: "Groceries",
      description: "Weekly groceries",
      pnl: -45
    }));

    view.unmount();
    const savingsSubmit = vi.fn();
    render(
      <CashTransactionForm
        account="Emergency"
        accountType="Savings"
        busy={false}
        currency="USD"
        onSubmit={savingsSubmit}
      />
    );
    fireEvent.change(screen.getByLabelText("Amount (USD)"), { target: { value: "100" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Monthly saving" } });
    fireEvent.click(screen.getByRole("button", { name: "Add transaction" }));
    expect(savingsSubmit).toHaveBeenCalledWith(expect.objectContaining({ category: "Savings", pnl: 100 }));
  });

  it("creates, edits, and deletes recurring bank transactions", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(
      <RecurringTransactionsPanel
        account="Current"
        busy={false}
        currency="EUR"
        feedback={{ tone: "success", message: "Automation created and saved to Firebase." }}
        onCreate={onCreate}
        onUpdate={onUpdate}
        onDelete={onDelete}
        schedules={[{
          id: "r1",
          account: "Current",
          action: "Withdraw",
          amount: 20,
          description: "Streaming",
          category: "Entertainment",
          day_of_month: 5,
          start_date: "2026-01-01",
          active: true
        }]}
      />
    );
    expect(screen.getByRole("status")).toHaveTextContent("Automation created and saved to Firebase.");
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Monthly salary" } });
    fireEvent.change(screen.getByLabelText("Transaction"), { target: { value: "Withdraw" } });
    fireEvent.change(screen.getByLabelText("Amount (EUR)"), { target: { value: "250" } });
    fireEvent.change(screen.getByLabelText("Day of month"), { target: { value: "31" } });
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-07-01" } });
    fireEvent.change(screen.getByLabelText("End date (optional)"), { target: { value: "2026-12-31" } });
    fireEvent.click(screen.getByRole("button", { name: "Rent & Housing" }));
    fireEvent.click(screen.getByRole("button", { name: "Create automation" }));
    expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({
      account: "Current",
      action: "Withdraw",
      amount: 250,
      category: "Rent & Housing",
      day_of_month: 31,
      start_date: "2026-07-01",
      end_date: "2026-12-31"
    }));
    fireEvent.click(screen.getByRole("button", { name: "Edit Streaming" }));
    expect(screen.getByLabelText("Description")).toHaveValue("Streaming");
    expect(screen.getByLabelText("Amount (EUR)")).toHaveValue(20);
    expect(screen.getByLabelText("Transaction")).toHaveValue("Withdraw");
    expect(screen.getByRole("button", { name: "Entertainment" })).toHaveClass("selected");
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Updated streaming" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(onUpdate).toHaveBeenCalledWith(expect.objectContaining({
      id: "r1",
      account: "Current",
      description: "Updated streaming",
      amount: 20
    }));

    fireEvent.click(screen.getByRole("button", { name: "Edit Streaming" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel editing" }));
    expect(screen.getByLabelText("Description")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Create automation" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Edit Streaming" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete Streaming" }));
    expect(onDelete).toHaveBeenCalledWith("r1");
    await waitFor(() => expect(screen.getByRole("button", { name: "Create automation" })).toBeInTheDocument());
  });

  it("keeps automation form values when Firebase rejects the request", async () => {
    const onCreate = vi.fn().mockRejectedValue(new Error("Firestore unavailable"));
    render(
      <RecurringTransactionsPanel
        account="Current"
        busy={false}
        currency="EUR"
        feedback={{ tone: "error", message: "Unable to save automation." }}
        onCreate={onCreate}
        onUpdate={vi.fn().mockResolvedValue(undefined)}
        onDelete={vi.fn().mockResolvedValue(undefined)}
        schedules={[]}
      />
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Unable to save automation.");
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Monthly salary" } });
    fireEvent.click(screen.getByRole("button", { name: "Create automation" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalled());
    expect(screen.getByLabelText("Description")).toHaveValue("Monthly salary");
  });

  it("does not submit incomplete cash or recurring transactions", () => {
    const cashSubmit = vi.fn();
    const recurringSubmit = vi.fn();
    const view = render(
      <CashTransactionForm
        account="Current"
        accountType="Bank Account"
        busy={false}
        currency="EUR"
        onSubmit={cashSubmit}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Add transaction" }));
    expect(cashSubmit).not.toHaveBeenCalled();
    view.unmount();

    render(
      <RecurringTransactionsPanel
        account="Current"
        busy={false}
        currency="EUR"
        onCreate={recurringSubmit}
        onUpdate={vi.fn().mockResolvedValue(undefined)}
        onDelete={vi.fn().mockResolvedValue(undefined)}
        schedules={[]}
      />
    );
    expect(screen.getByText("No recurring transactions configured.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create automation" }));
    expect(recurringSubmit).not.toHaveBeenCalled();
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

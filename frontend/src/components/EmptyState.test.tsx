import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders its title and explanatory text", () => {
    render(<EmptyState title="No trades yet" body="Add a trade to populate this view." />);

    expect(screen.getByRole("heading", { name: "No trades yet" })).toBeInTheDocument();
    expect(screen.getByText("Add a trade to populate this view.")).toBeInTheDocument();
  });
});

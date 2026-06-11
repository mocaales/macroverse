import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricStrip } from "./MetricStrip";

describe("MetricStrip", () => {
  it("renders metric values, details, and tones", () => {
    render(
      <MetricStrip
        metrics={[
          {
            label: "Realised P&L",
            value: "$125.00",
            detail: "Across 4 trades",
            tone: "positive"
          },
          {
            label: "Win rate",
            value: "75%"
          }
        ]}
      />
    );

    expect(screen.getByText("Realised P&L")).toBeInTheDocument();
    expect(screen.getByText("$125.00")).toHaveClass("positive");
    expect(screen.getByText("Across 4 trades")).toBeInTheDocument();
    expect(screen.getByText("75%")).toHaveClass("neutral");
  });
});

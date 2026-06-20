export type BalanceDeltaTone = "positive" | "negative" | "neutral";

export function balanceDeltaTone(value: number): BalanceDeltaTone {
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "neutral";
}

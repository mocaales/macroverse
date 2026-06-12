import type { ChartSeries } from "../../types";

export interface AnnualRoiSeries {
  year: number;
  points: Array<{ day: number; date: string; roi: number; price: number }>;
}

export type PresidentialCycle = "all" | "post-election" | "midterm" | "pre-election" | "election";

export function presidentialCycle(year: number): Exclude<PresidentialCycle, "all"> {
  const cycle = ((year % 4) + 4) % 4;
  if (cycle === 0) return "election";
  if (cycle === 1) return "post-election";
  if (cycle === 2) return "midterm";
  return "pre-election";
}

export function matchesPresidentialCycle(year: number, cycle: PresidentialCycle) {
  return cycle === "all" || presidentialCycle(year) === cycle;
}

function normalizedDay(date: string): number | null {
  const monthDay = date.slice(5, 10);
  if (monthDay === "02-29") return null;
  const reference = new Date(`${date.slice(0, 4)}-${monthDay}T00:00:00Z`);
  const normalized = new Date(`2001-${monthDay}T00:00:00Z`);
  if (Number.isNaN(reference.getTime()) || Number.isNaN(normalized.getTime())) return null;
  return Math.floor((normalized.getTime() - Date.UTC(2001, 0, 1)) / 86_400_000);
}

export function buildAnnualRoiSeries(series: ChartSeries[]): AnnualRoiSeries[] {
  const rows = series[0]?.points || [];
  const grouped = new Map<number, typeof rows>();
  rows.forEach((point) => {
    const year = Number(point.date.slice(0, 4));
    if (!Number.isFinite(year) || point.value <= 0) return;
    grouped.set(year, [...(grouped.get(year) || []), point]);
  });

  return [...grouped.entries()]
    .sort(([left], [right]) => left - right)
    .flatMap(([year, points]) => {
      const ordered = [...points].sort((left, right) => left.date.localeCompare(right.date));
      const base = ordered[0]?.value;
      if (!base) return [];
      const unique = new Map<number, AnnualRoiSeries["points"][number]>();
      ordered.forEach((point) => {
        const day = normalizedDay(point.date);
        if (day === null) return;
        unique.set(day, {
          day,
          date: point.date,
          roi: (point.value / base - 1) * 100,
          price: point.value
        });
      });
      return [{ year, points: [...unique.values()].sort((left, right) => left.day - right.day) }];
    });
}

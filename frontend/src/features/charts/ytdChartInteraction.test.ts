import { describe, expect, it } from "vitest";

import {
  clamp,
  horizontalZoomRange,
  interpolateRange,
  isRangeSettled,
  normalizedWheelDelta,
  scaleAutoscaleInfo,
  verticalZoom,
  wheelDeltaUnit
} from "./ytdChartInteraction";

describe("YTD chart interaction helpers", () => {
  it("clamps values and normalizes wheel units", () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(-1, 0, 10)).toBe(0);
    expect(clamp(11, 0, 10)).toBe(10);
    expect(wheelDeltaUnit(WheelEvent.DOM_DELTA_PIXEL, 500)).toBe(1);
    expect(wheelDeltaUnit(WheelEvent.DOM_DELTA_LINE, 500)).toBe(16);
    expect(wheelDeltaUnit(WheelEvent.DOM_DELTA_PAGE, 500)).toBe(500);
    expect(normalizedWheelDelta(20, WheelEvent.DOM_DELTA_LINE, 500)).toBe(120);
    expect(normalizedWheelDelta(-20, WheelEvent.DOM_DELTA_LINE, 500)).toBe(-120);
  });

  it("scales positive logarithmic ranges and preserves invalid ranges", () => {
    const base = { priceRange: { minValue: 10, maxValue: 1_000 } };
    const scaled = scaleAutoscaleInfo(base, 0.5);

    expect(scaled?.priceRange?.minValue).toBeCloseTo(31.6228);
    expect(scaled?.priceRange?.maxValue).toBeCloseTo(316.2277);
    expect(scaleAutoscaleInfo(null, 2)).toBeNull();
    expect(scaleAutoscaleInfo({ priceRange: { minValue: 0, maxValue: 10 } }, 2))
      .toEqual({ priceRange: { minValue: 0, maxValue: 10 } });
  });

  it("interpolates and detects settled ranges", () => {
    const next = interpolateRange({ from: 0, to: 100 }, { from: 20, to: 80 }, 0.25);

    expect(next).toEqual({ from: 5, to: 95 });
    expect(isRangeSettled(next, { from: 5.01, to: 95.01 })).toBe(true);
    expect(isRangeSettled(next, { from: 6, to: 95 })).toBe(false);
  });

  it("zooms horizontally around the pointer without leaving the data bounds", () => {
    expect(horizontalZoomRange({ from: 20, to: 80 }, { from: 0, to: 100 }, 0.5, 0.5))
      .toEqual({ from: 35, to: 65 });
    expect(horizontalZoomRange({ from: 0, to: 20 }, { from: 0, to: 100 }, 0, 2))
      .toEqual({ from: 0, to: 40 });
    expect(horizontalZoomRange({ from: 80, to: 100 }, { from: 0, to: 100 }, 1, 2))
      .toEqual({ from: 60, to: 100 });
    expect(horizontalZoomRange({ from: 20, to: 80 }, { from: 0, to: 100 }, 2, 10))
      .toEqual({ from: 0, to: 100 });
  });

  it("constrains vertical zoom to the supported scale", () => {
    expect(verticalZoom(1, 2)).toBe(2);
    expect(verticalZoom(1, 0.01)).toBe(0.18);
    expect(verticalZoom(1, 10)).toBe(5);
  });
});

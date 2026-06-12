import type { AutoscaleInfo } from "lightweight-charts";

export interface NumericRange {
  from: number;
  to: number;
}

const MIN_HORIZONTAL_SPAN = 8;
const MIN_VERTICAL_ZOOM = 0.18;
const MAX_VERTICAL_ZOOM = 5;

export function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), maximum);
}

export function scaleAutoscaleInfo(base: AutoscaleInfo | null, zoom: number): AutoscaleInfo | null {
  const range = base?.priceRange;
  if (!base || !range || range.minValue <= 0 || range.maxValue <= 0) return base;

  const minLog = Math.log(range.minValue);
  const maxLog = Math.log(range.maxValue);
  const center = (minLog + maxLog) / 2;
  const halfSpan = ((maxLog - minLog) / 2) * zoom;

  return {
    ...base,
    priceRange: {
      minValue: Math.exp(center - halfSpan),
      maxValue: Math.exp(center + halfSpan)
    }
  };
}

export function interpolateRange(current: NumericRange, target: NumericRange, smoothing: number): NumericRange {
  return {
    from: current.from + (target.from - current.from) * smoothing,
    to: current.to + (target.to - current.to) * smoothing
  };
}

export function isRangeSettled(current: NumericRange, target: NumericRange, tolerance = 0.015) {
  return Math.abs(target.from - current.from) <= tolerance
    && Math.abs(target.to - current.to) <= tolerance;
}

export function wheelDeltaUnit(deltaMode: number, containerHeight: number) {
  if (deltaMode === WheelEvent.DOM_DELTA_LINE) return 16;
  if (deltaMode === WheelEvent.DOM_DELTA_PAGE) return containerHeight;
  return 1;
}

export function normalizedWheelDelta(deltaY: number, deltaMode: number, containerHeight: number) {
  return clamp(deltaY * wheelDeltaUnit(deltaMode, containerHeight), -120, 120);
}

export function horizontalZoomRange(
  range: NumericRange,
  fullRange: NumericRange,
  pointerRatio: number,
  factor: number
): NumericRange {
  const ratio = clamp(pointerRatio, 0, 1);
  const currentSpan = range.to - range.from;
  const fullSpan = fullRange.to - fullRange.from;
  const nextSpan = clamp(currentSpan * factor, Math.min(MIN_HORIZONTAL_SPAN, fullSpan), fullSpan);
  const anchor = range.from + currentSpan * ratio;
  let from = anchor - nextSpan * ratio;
  let to = from + nextSpan;

  if (from < fullRange.from) {
    from = fullRange.from;
    to = from + nextSpan;
  }
  if (to > fullRange.to) {
    to = fullRange.to;
    from = to - nextSpan;
  }

  return { from, to };
}

export function verticalZoom(current: number, factor: number) {
  return clamp(current * factor, MIN_VERTICAL_ZOOM, MAX_VERTICAL_ZOOM);
}

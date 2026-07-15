import { buildAnalyticsRange, formatCompactNumber, formatCost, percentage } from "./presentation";

describe("observability presentation", () => {
  it("builds a stable UTC range", () => {
    const range = buildAnalyticsRange(7, new Date("2026-07-14T00:00:00.000Z"));
    expect(range.startAt).toBe("2026-07-07T00:00:00.000Z");
    expect(range.endAt).toBe("2026-07-14T00:00:00.000Z");
  });

  it("formats dashboard values", () => {
    expect(formatCompactNumber(12500)).toContain("1.3万");
    expect(formatCost(0.12345, "CNY")).toBe("¥0.1235");
    expect(percentage(0.9876)).toBe("98.8%");
  });
});

export function buildAnalyticsRange(days: number, now = new Date()) {
  return {
    startAt: new Date(now.getTime() - days * 24 * 60 * 60 * 1000).toISOString(),
    endAt: now.toISOString(),
  };
}

export function formatCompactNumber(value: number | null | undefined): string {
  return new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);
}

export function formatCost(value: number | null | undefined, currency?: string | null): string {
  const prefix = currency === "CNY" ? "¥" : currency === "USD" ? "$" : "";
  return `${prefix}${Number(value || 0).toFixed(4)}`;
}

export function percentage(value: number | null | undefined): string {
  return `${((value || 0) * 100).toFixed(1)}%`;
}

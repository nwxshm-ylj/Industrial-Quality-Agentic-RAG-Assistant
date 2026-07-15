interface MetricSparklineProps {
  values: number[];
  color?: string;
}

export function MetricSparkline({ values, color = "#0a8f86" }: MetricSparklineProps) {
  const width = 600;
  const height = 150;
  const safeValues = values.length ? values : [0];
  const max = Math.max(...safeValues, 1);
  const min = Math.min(...safeValues, 0);
  const range = Math.max(max - min, 1);
  const points = safeValues.map((value, index) => {
    const x = safeValues.length === 1 ? width / 2 : (index / (safeValues.length - 1)) * width;
    const y = height - 12 - ((value - min) / range) * (height - 24);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  return (
    <svg className="metric-sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="指标趋势图">
      <defs>
        <linearGradient id={`gradient-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.22" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <line x1="0" y1="138" x2="600" y2="138" stroke="#e2e9ec" strokeWidth="1" />
      <polygon points={`0,150 ${points} 600,150`} fill={`url(#gradient-${color.replace("#", "")})`} />
      <polyline points={points} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

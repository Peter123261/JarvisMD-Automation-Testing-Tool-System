export interface MetricEntry {
  line: string;
  value: number;
  labels: string;
  source?: string;
}

export type ParsedMetricsMap = Record<string, MetricEntry[]> | undefined;

export function sumMetric(parsed: ParsedMetricsMap, name: string): number {
  if (!parsed || !parsed[name]) return 0;
  return parsed[name].reduce((total, entry) => total + (entry.value ?? 0), 0);
}

export function computeHistogramQuantile(
  parsed: ParsedMetricsMap,
  metricName: string,
  quantile: number
): number {
  if (!parsed || !parsed[metricName]?.length) return 0;

  const buckets = parsed[metricName]
    .map((entry) => {
      const match = entry.labels.match(/le="([^"]+)"/);
      const leRaw = match ? match[1] : '+Inf';
      const le = leRaw === '+Inf' ? Number.POSITIVE_INFINITY : Number(leRaw);
      return { le, value: entry.value ?? 0 };
    })
    .sort((a, b) => a.le - b.le);

  const total = buckets[buckets.length - 1]?.value ?? 0;
  if (!total) return 0;

  const target = total * quantile;

  for (const bucket of buckets) {
    if (bucket.value >= target) {
      return Number.isFinite(bucket.le) ? bucket.le : buckets[buckets.length - 2]?.le ?? 0;
    }
  }

  return 0;
}

export const formatPercent = (value: number, fractionDigits = 1): string =>
  `${Math.max(0, Math.min(100, value)).toFixed(fractionDigits)}%`;

export const formatSeconds = (value: number, fractionDigits = 1): string =>
  value <= 0 ? 'N/A' : `${value.toFixed(fractionDigits)}s`;

export const formatCurrency = (value: number, fractionDigits = 2): string =>
  `$${value.toFixed(fractionDigits)}`;


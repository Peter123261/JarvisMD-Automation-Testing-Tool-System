import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  CircularProgress,
  Alert,
  Button,
  Stack,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  AccessTime as AccessTimeIcon,
  ShowChart as ShowChartIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Legend,
} from 'recharts';
import { SummaryCard } from '../components/common';
import apiService from '../services/api';
import {
  computeHistogramQuantile,
  formatPercent,
  formatSeconds,
  sumMetric,
} from '../utils/metrics';
import type { ParsedMetricsMap } from '../utils/metrics';

interface JobSummary {
  success_rate: number;
  success_count: number;
  failure_count: number;
  flagged_cases: number;
  p95_duration_seconds: number;
  average_duration_seconds: number;
  estimated_cost: number;
  cost_per_call: number;
  cases_processed: number;
  total_cases: number;
}

interface LatestJobMetricsResponse {
  job: {
    id: string;
    benchmark: string;
    model: string;
    total_cases: number;
    processed_cases: number;
    status: string;
    start_time?: string | null;
    end_time?: string | null;
  };
  summary: JobSummary;
  tokens: {
    input: number;
    output: number;
    total: number;
  };
  durations: {
    count: number;
    min: number;
    max: number;
    sum: number;
  };
  cases: Array<{
    order: number;
    case_id: string;
    score: number;
    processing_time: number;
    flagged: boolean;
    prompt_tokens?: number | null;
    completion_tokens?: number | null;
    total_tokens?: number | null;
    created_at?: string | null;
  }>;
}

interface CostMetrics {
  total_calls: number;
  total_tokens: number;
  estimated_cost: number;
  cost_per_call: number;
  average_tokens_per_call: number;
  total_duration: number;
  average_duration: number;
  min_duration: number;
  max_duration: number;
  success_rate: number;
  successful_calls: number;
  failed_calls: number;
}

interface MetricsResponse {
  timestamp: string;
  cost_metrics: CostMetrics;
  prometheus_metrics?: {
    parsed_metrics?: ParsedMetricsMap;
    combined_totals?: Record<string, number>;
    raw_metrics?: string;
  };
}

interface HistoryPoint {
  timestamp: string;
  successRate: number;
  p95: number;
  flaggedPerMinute: number;
}

interface DerivedSample {
  timestampMs: number;
  flaggedTotal: number;
}

const REFRESH_INTERVAL_MS = 60_000;
const MAX_HISTORY_POINTS = 60;

const Analytics: React.FC = () => {
  const {
    data: latestJobData,
    isLoading: isLatestLoading,
    error: latestError,
  } = useQuery<LatestJobMetricsResponse>({
    queryKey: ['latestJobMetrics'],
    queryFn: () => apiService.getLatestJobMetrics(),
    refetchInterval: REFRESH_INTERVAL_MS,
  });

  const { data: lifetimeData } = useQuery<MetricsResponse>({
    queryKey: ['metrics'],
    queryFn: apiService.getMetrics,
    refetchInterval: REFRESH_INTERVAL_MS,
  });

  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const previousRef = useRef<DerivedSample | null>(null);

  const parsedMetrics = lifetimeData?.prometheus_metrics?.parsed_metrics;
  const combinedTotals = lifetimeData?.prometheus_metrics?.combined_totals ?? {};
  const costMetrics = lifetimeData?.cost_metrics;

  const successTotal = useMemo(() => {
    const combinedValue = combinedTotals['evaluations_success_total'];
    if (typeof combinedValue === 'number') return combinedValue;
    return sumMetric(parsedMetrics, 'evaluations_success_total');
  }, [combinedTotals, parsedMetrics]);

  const failedTotal = useMemo(() => {
    const combinedValue = combinedTotals['evaluations_failed_total'];
    if (typeof combinedValue === 'number') return combinedValue;
    return sumMetric(parsedMetrics, 'evaluations_failed_total');
  }, [combinedTotals, parsedMetrics]);
  const totalEvaluations = successTotal + failedTotal;
  const aggregatedSuccessRate = totalEvaluations > 0
    ? (successTotal / totalEvaluations) * 100
    : costMetrics?.success_rate ?? 0;

  const aggP95 = useMemo(() => {
    const histogramP95 = computeHistogramQuantile(
      parsedMetrics,
      'evaluation_duration_seconds_bucket',
      0.95
    );
    if (histogramP95 > 0 && Number.isFinite(histogramP95)) {
      return histogramP95;
    }
    const fallback = costMetrics?.max_duration ?? 0;
    return fallback;
  }, [parsedMetrics, costMetrics?.max_duration]);

  const flaggedTotal = useMemo(() => {
    const combinedValue = combinedTotals['cases_flagged_total'];
    if (typeof combinedValue === 'number') return combinedValue;
    return sumMetric(parsedMetrics, 'cases_flagged_total');
  }, [combinedTotals, parsedMetrics]);

  const durationSum = useMemo(() => {
    const combinedValue = combinedTotals['evaluation_duration_seconds_sum'];
    if (typeof combinedValue === 'number') return combinedValue;
    return sumMetric(parsedMetrics, 'evaluation_duration_seconds_sum');
  }, [combinedTotals, parsedMetrics]);

  const durationCount = useMemo(() => {
    const combinedValue = combinedTotals['evaluation_duration_seconds_count'];
    if (typeof combinedValue === 'number') return combinedValue;
    return sumMetric(parsedMetrics, 'evaluation_duration_seconds_count');
  }, [combinedTotals, parsedMetrics]);
  const aggregatedAverageDuration =
    durationCount > 0 ? durationSum / durationCount : costMetrics?.average_duration ?? 0;

  useEffect(() => {
    if (!lifetimeData) return;

    const timestampMs = new Date(lifetimeData.timestamp).getTime();
    if (Number.isNaN(timestampMs)) {
      return;
    }

    const previous = previousRef.current;
    let flaggedPerMinute = 0;
    if (previous) {
      const deltaMinutes = (timestampMs - previous.timestampMs) / 60_000;
      if (deltaMinutes > 0) {
        flaggedPerMinute = Math.max(0, (flaggedTotal - previous.flaggedTotal) / deltaMinutes);
      }
    }

    const newPoint: HistoryPoint = {
      timestamp: new Date(timestampMs).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      }),
      successRate: aggregatedSuccessRate,
      p95: aggP95,
      flaggedPerMinute,
    };

    setHistory((prev) => {
      const next = [...prev, newPoint];
      if (next.length > MAX_HISTORY_POINTS) {
        next.shift();
      }
      return next;
    });

    previousRef.current = {
      timestampMs,
      flaggedTotal,
    };
  }, [lifetimeData, aggregatedSuccessRate, aggP95, flaggedTotal]);

  if (isLatestLoading) {
    return (
      <Box display="flex" justifyContent="center" minHeight="60vh" alignItems="center">
        <CircularProgress />
      </Box>
    );
  }

  if (latestError) {
    return <Alert severity="error">Failed to load analytics: {(latestError as Error).message}</Alert>;
  }

  if (!latestJobData) {
    return <Alert severity="warning">No metrics available yet. Run an evaluation to populate data.</Alert>;
  }

  const jobSummary = latestJobData.summary;
  const jobTokens = latestJobData.tokens;
  const totalFlagged = jobSummary.flagged_cases;
  const tokensToday = jobTokens.total;
  const successfulEvaluations = jobSummary.success_count;
  const failedEvaluations = jobSummary.failure_count;

  const successRateDisplay = jobSummary.success_rate;
  const p95Display = jobSummary.p95_duration_seconds;

  const grafanaUrl = import.meta.env.VITE_GRAFANA_URL || 'http://localhost:3000';

  return (
    <Box>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Analytics
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Real-time insights into evaluation performance, cost, and safety.
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<ShowChartIcon />}
          href={grafanaUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open in Grafana
        </Button>
      </Box>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <SummaryCard
            title="Success Rate"
            value={formatPercent(successRateDisplay)}
            subtitle="Latest completed job"
            icon={<TrendingUpIcon />}
            color="success"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <SummaryCard
            title="P95 Duration"
            value={formatSeconds(p95Display)}
            subtitle="95% of cases finish within"
            icon={<AccessTimeIcon />}
            color={p95Display > 60 ? 'warning' : 'info'}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <SummaryCard
            title="Tokens Processed"
            value={tokensToday.toLocaleString()}
            subtitle={`Input ${jobTokens.input.toLocaleString()} • Output ${jobTokens.output.toLocaleString()}`}
            icon={<TrendingUpIcon />}
            color="primary"
          />
        </Grid>
      </Grid>

      <Grid container spacing={3} mt={1}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 3, height: 360 }}>
            <Typography variant="h6" gutterBottom>
              Success Rate Trend
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Sampling every minute (lower values indicate failed evaluations).
            </Typography>
            <ResponsiveContainer width="100%" height="85%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis domain={[0, 100]} tickFormatter={(val) => `${val}%`} />
                <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
                <Line type="monotone" dataKey="successRate" stroke="#2e7d32" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 3, height: 360 }}>
            <Typography variant="h6" gutterBottom>
              Latency (P95) Trend
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Higher spikes indicate slower evaluations.
            </Typography>
            <ResponsiveContainer width="100%" height="85%">
              <AreaChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis unit="s" tickFormatter={(val) => `${val}s`} />
                <Tooltip formatter={(value: number) => `${value.toFixed(1)}s`} />
                <Area type="monotone" dataKey="p95" stroke="#0288d1" fill="#0288d1" fillOpacity={0.2} />
              </AreaChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: 3, height: 360 }}>
            <Typography variant="h6" gutterBottom>
              Flagged Cases per Minute
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Calculated from the cases-flagged counter.
            </Typography>
            <ResponsiveContainer width="100%" height="85%">
              <BarChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip formatter={(value: number) => value.toFixed(2)} />
                <Legend />
                <Bar dataKey="flaggedPerMinute" fill="#ef6c00" name="Flagged/min" />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

      </Grid>
    </Box>
  );
};

export default Analytics;


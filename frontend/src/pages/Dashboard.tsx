/**
 * Dashboard Page
 * System overview with health status and quick actions
 */

import { useState, useEffect } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Grid,
  Paper,
  Typography,
} from '@mui/material';
import {
  Assessment as AssessmentIcon,
  CheckCircle as CheckCircleIcon,
  PlayArrow as PlayArrowIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import { SummaryCard } from '../components/common';

export default function Dashboard() {
  const navigate = useNavigate();
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [caseCount, setCaseCount] = useState<any>(null);
  const [latestJobSummary, setLatestJobSummary] = useState<any>(null);
  const [latestJobMetrics, setLatestJobMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [health, cases, summary, metrics] = await Promise.all([
          apiService.checkHealth(),
          apiService.getCaseCount(),
          apiService.getResultsSummary(),
          apiService.getLatestJobMetrics(),
        ]);
        setHealthStatus(health);
        setCaseCount(cases);
        setLatestJobSummary(summary);
        setLatestJobMetrics(metrics);
      } catch (err: any) {
        console.error('Failed to load dashboard data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
    
        // Auto-refresh every 1 minute to catch new evaluations
        const interval = setInterval(loadData, 60000);
    
    return () => clearInterval(interval);
  }, []);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Typography variant="body1" color="text.secondary" gutterBottom>
        System overview and quick actions
      </Typography>

      {loading && (
        <Box display="flex" justifyContent="center" minHeight="60vh" alignItems="center">
          <CircularProgress />
        </Box>
      )}

      {!loading && error && <Alert severity="error">Failed to load dashboard: {error}</Alert>}

      {!loading && !error && (
        <>
      <Grid container spacing={3} sx={{ mt: 2 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <SummaryCard
            title="System Health"
            value={healthStatus?.status || 'Unknown'}
            subtitle="All systems operational"
            icon={<CheckCircleIcon />}
            color="success"
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <SummaryCard
            title="Available Cases"
            value={caseCount?.total_cases || 0}
            subtitle="Ready for evaluation"
            icon={<AssessmentIcon />}
            color="primary"
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <SummaryCard
            title="Latest Job Cases"
            value={latestJobSummary?.total_evaluations ?? 0}
            subtitle="Cases in most recent evaluation"
            icon={<PlayArrowIcon />}
            color="info"
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <SummaryCard
            title="Latest Job Score"
            value={
              latestJobSummary
                ? `${(latestJobSummary.average_score ?? 0).toFixed(1)}%`
                : 'N/A'
            }
            subtitle={`Flagged: ${latestJobSummary?.cases_flagged_for_review ?? 0} cases`}
            icon={<WarningIcon />}
            color={
              (latestJobSummary?.cases_flagged_for_review ?? 0) > 0 ? 'warning' : 'success'
            }
          />
        </Grid>
      </Grid>

      {latestJobMetrics?.job && (
        <Paper sx={{ p: 3, mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            Latest Evaluation Job
          </Typography>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Typography variant="body2" color="text.secondary">Job ID</Typography>
              <Typography variant="body1" fontFamily="monospace" sx={{ wordBreak: 'break-all' }}>
                {latestJobMetrics.job.id}
              </Typography>
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Typography variant="body2" color="text.secondary">Model</Typography>
              <Typography variant="body1">{latestJobMetrics.job.model}</Typography>
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Typography variant="body2" color="text.secondary">Completed</Typography>
              <Typography variant="body1">
                {latestJobMetrics.job.end_time
                  ? new Date(latestJobMetrics.job.end_time).toLocaleString()
                  : 'In progress'}
              </Typography>
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Typography variant="body2" color="text.secondary">Success Rate</Typography>
              <Typography variant="body1">
                {(latestJobMetrics.summary?.success_rate ?? 0).toFixed(1)}%
              </Typography>
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Typography variant="body2" color="text.secondary">Tokens</Typography>
              <Typography variant="body1">
                Input {latestJobMetrics.tokens?.input ?? 0} • Output {latestJobMetrics.tokens?.output ?? 0} • Total {latestJobMetrics.tokens?.total ?? 0}
              </Typography>
            </Grid>
          </Grid>
        </Paper>
      )}

      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="h6" gutterBottom>
          Quick Actions
        </Typography>
        <Box display="flex" gap={2} mt={2}>
          <Button
            variant="contained"
            startIcon={<PlayArrowIcon />}
            onClick={() => navigate('/test')}
          >
            Start New Evaluation
          </Button>
          <Button
            variant="outlined"
            startIcon={<AssessmentIcon />}
            onClick={() => navigate('/results')}
          >
            View Results
          </Button>
        </Box>
      </Paper>
        </>
      )}
    </Box>
  );
}

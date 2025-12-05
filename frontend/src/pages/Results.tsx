import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  LinearProgress,
  TextField,
  Typography,
  Paper,
} from '@mui/material';
import {
  Assessment,
  Close as CloseIcon,
  Download as DownloadIcon,
  TrendingUp,
  Warning,
  FilterList as FilterListIcon,
  Clear as ClearIcon,
  Timeline as TimelineIcon,
  OpenInNew as OpenInNewIcon,
  ContentCopy as ContentCopyIcon,
} from '@mui/icons-material';
import {
  DataTable,
  EmptyState,
  LoadingSkeleton,
  StatusBadge,
  SummaryCard,
} from '../components/common';
import type { Column } from '../components/common/DataTable';
import { apiService } from '../services/api';

interface SummaryData {
  total_evaluations: number;
  average_score: number;
  cases_flagged_for_review: number;
}

interface RecentJobRow {
  job_id: string;
  status: string;
  benchmark: string;
  model: string;
  total_cases: number;
  processed_cases: number;
  successful_evaluations: number;
  failed_evaluations: number;
  start_time?: string | null;
  end_time?: string | null;
  duration_minutes?: number | null;
}

interface DetailedResult {
  case_id: string;
  doctor_name: string;
  case_name: string;
  total_score: number;
  criteria_scores: Record<string, number>;
  processing_time: number;
  created_at: string;
  complexity_level?: string;
  flagged_for_review: boolean;
  review_priority: string;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  evaluation_text?: string | null; // Full OpenAI response (prompt-defined structure)
  trace_id?: string | null; // OpenTelemetry trace ID
}

interface CriterionSchema {
  id: number;
  name: string;
  description: string;
  max_score: number;
  is_safety: boolean;
}

interface JobResultsResponse {
  job_id: string;
  summary: {
    total_evaluations: number;
    average_score: number;
    benchmark: string;
    model: string;
    completion_time?: string | null;
    cases_flagged_for_review: number;
    review_threshold?: number;
  };
  detailed_results: DetailedResult[];
  criteria_schema?: CriterionSchema[] | null; // Full criteria schema - canonical source of truth
  criterion_max_scores?: Record<number, number> | null; // Deprecated, use criteria_schema
  criterion_name_to_max_score?: Record<string, number> | null; // Deprecated, use criteria_schema
}

const REFRESH_INTERVAL_MS = 60_000;

export default function Results() {
  const [jobs, setJobs] = useState<RecentJobRow[]>([]);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [filters, setFilters] = useState({
    job_id: '',
  });

  const [detailsOpen, setDetailsOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<RecentJobRow | null>(null);
  const [selectedJobDetails, setSelectedJobDetails] = useState<JobResultsResponse | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState<string | null>(null);


  useEffect(() => {
    void fetchData();
    const interval = setInterval(() => {
      void fetchData();
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [filters]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Build filter params (only include non-empty filters)
      const filterParams: any = {};
      if (filters.job_id.trim()) {
        filterParams.job_id = filters.job_id.trim();
      }

      if (filters.job_id.trim()) {
        // When filtering by job_id, fetch that specific job's data
        const [summaryResponse, jobStatusResponse] = await Promise.all([
          apiService.getResultsSummary(filterParams),
          apiService.getEvaluationStatus(filters.job_id.trim()).catch(() => null),
        ]);

        setSummary({
          total_evaluations: summaryResponse?.total_evaluations ?? 0,
          average_score: summaryResponse?.average_score ?? 0,
          cases_flagged_for_review: summaryResponse?.cases_flagged_for_review ?? 0,
        });

        // If we got job status, create a job row for the table
        if (jobStatusResponse) {
          setJobs([{
            job_id: filters.job_id.trim(),
            status: jobStatusResponse.status || 'unknown',
            benchmark: jobStatusResponse.benchmark || summaryResponse?.benchmark || 'unknown',
            model: jobStatusResponse.model || summaryResponse?.model || 'unknown',
            total_cases: jobStatusResponse.total_cases || summaryResponse?.total_evaluations || 0,
            processed_cases: summaryResponse?.total_evaluations || 0,
            successful_evaluations: summaryResponse?.total_evaluations - (summaryResponse?.cases_flagged_for_review || 0),
            failed_evaluations: 0,
            start_time: jobStatusResponse.start_time,
            end_time: jobStatusResponse.end_time || summaryResponse?.completion_time,
            duration_minutes: null,
          }]);
        } else {
          // Job not found or error - show empty jobs but keep summary
          setJobs([]);
        }
      } else {
        // No filter - show recent jobs
        const [summaryResponse, jobsResponse] = await Promise.all([
          apiService.getResultsSummary(undefined),
          apiService.getRecentJobs(10),
        ]);

        setSummary({
          total_evaluations: summaryResponse?.total_evaluations ?? 0,
          average_score: summaryResponse?.average_score ?? 0,
          cases_flagged_for_review: summaryResponse?.cases_flagged_for_review ?? 0,
        });

        setJobs(jobsResponse?.recent_jobs ?? []);
      }
    } catch (err: any) {
      console.error('Error fetching results:', err);
      setError(err?.message ?? 'Failed to fetch results');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (field: keyof typeof filters, value: string) => {
    setFilters((prev) => ({ ...prev, [field]: value }));
  };

  const handleClearFilters = () => {
    setFilters({
      job_id: '',
    });
  };

  const hasActiveFilters = filters.job_id.trim() !== '';

  const handleViewDetails = async (job: RecentJobRow) => {
    setSelectedJob(job);
    setDetailsOpen(true);
    setDetailsLoading(true);
    setDetailsError(null);
    setSelectedJobDetails(null);

    try {
      const jobDetails = await apiService.getEvaluationResults(job.job_id);
      // Debug: Inspect the full job details including per-case criteria_scores
      console.log('Loaded job details for job:', job.job_id, jobDetails);
      setSelectedJobDetails(jobDetails);
    } catch (err: any) {
      console.error('Failed to load job details:', err);
      setDetailsError(err?.message ?? 'Failed to load job details');
    } finally {
      setDetailsLoading(false);
    }
  };

  const handleCloseDetails = () => {
    setDetailsOpen(false);
    setSelectedJob(null);
    setSelectedJobDetails(null);
    setDetailsError(null);
  };

  const handleDownloadResults = () => {
    if (!selectedJobDetails) return;

    // Export prompt-defined structure directly - no hardcoded restructuring
    // The evaluation_text contains the structure defined by the prompt file
    const downloadData = {
      job_id: selectedJobDetails.job_id,
      job_summary: {
        total_evaluations: selectedJobDetails.summary.total_evaluations,
        average_score: selectedJobDetails.summary.average_score,
        benchmark: selectedJobDetails.summary.benchmark,
        model: selectedJobDetails.summary.model,
        completion_time: selectedJobDetails.summary.completion_time,
        cases_flagged_for_review: selectedJobDetails.summary.cases_flagged_for_review,
        review_threshold: selectedJobDetails.summary.review_threshold,
      },
      cases: selectedJobDetails.detailed_results.map((result) => {
        // Parse evaluation_text to get the prompt-defined structure
        let evaluation = null;
        if (result.evaluation_text) {
          try {
            evaluation = JSON.parse(result.evaluation_text);
            // Remove LLM's percentage fields to avoid confusion
            // We use the database-calculated average_score instead
            if (evaluation && typeof evaluation === 'object') {
              // Remove overall_percentage from evaluation_summary
              if (evaluation.evaluation_summary && 'overall_percentage' in evaluation.evaluation_summary) {
                delete evaluation.evaluation_summary.overall_percentage;
              }
              // Remove final_percentage from final_validation
              if (evaluation.final_validation && 'final_percentage' in evaluation.final_validation) {
                delete evaluation.final_validation.final_percentage;
              }
            }
          } catch (e) {
            // If parsing fails, evaluation_text remains as string
            evaluation = result.evaluation_text;
          }
        }

        return {
          case_id: result.case_id,
          doctor_name: result.doctor_name,
          case_name: result.case_name,
          total_score: result.total_score,
          criteria_scores: result.criteria_scores,
          // Export the prompt-defined structure directly from evaluation_text
          // This structure is determined by the prompt file, not hardcoded
          // Note: overall_percentage and final_percentage have been removed to avoid confusion
          // We use the database-calculated average_score (in job_summary) as the authoritative metric
          evaluation: evaluation,
          evaluation_text: result.evaluation_text, // Also include raw text for reference
          processing_time: result.processing_time,
          created_at: result.created_at,
          complexity_level: result.complexity_level,
          flagged_for_review: result.flagged_for_review,
          review_priority: result.review_priority,
          prompt_tokens: result.prompt_tokens,
          completion_tokens: result.completion_tokens,
          total_tokens: result.total_tokens,
        };
      }),
      exported_at: new Date().toISOString(),
    };

    // Create a blob and download
    const jsonString = JSON.stringify(downloadData, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `evaluation_results_${selectedJobDetails.job_id}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const columns: Column[] = [
    {
      id: 'job_id',
      label: 'Job ID',
      minWidth: 220,
      format: (value: any) => (
        <Typography variant="body2" fontFamily="monospace">
          {value}
        </Typography>
      ),
    },
    {
      id: 'total_cases',
      label: 'Cases',
      minWidth: 80,
      align: 'center',
      format: (value: any) => value ?? 0,
    },
    {
      id: 'processed_cases',
      label: 'Processed',
      minWidth: 110,
      align: 'center',
      format: (value: any) => value ?? 0,
    },
    {
      id: 'successful_evaluations',
      label: 'Successful',
      minWidth: 110,
      align: 'center',
      format: (value: any) => (
        <Typography variant="body2" color="success.main">
          {value ?? 0}
        </Typography>
      ),
    },
    {
      id: 'failed_evaluations',
      label: 'Failed',
      minWidth: 90,
      align: 'center',
      format: (value: any) => (
        <Typography variant="body2" color={value > 0 ? 'error.main' : 'text.primary'}>
          {value ?? 0}
        </Typography>
      ),
    },
    {
      id: 'end_time',
      label: 'Completed At',
      minWidth: 200,
      format: (value: any) => (value ? new Date(value).toLocaleString() : '—'),
    },
    {
      id: 'actions',
      label: 'Actions',
      minWidth: 130,
      align: 'center',
      format: (_value: any, row: any) => (
        <Button variant="contained" size="small" onClick={(e) => { e.stopPropagation(); handleViewDetails(row); }}>
          View Cases
        </Button>
      ),
    },
  ];

  if (loading) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Results
        </Typography>
        <LoadingSkeleton variant="card" count={3} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Results
        </Typography>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  // Only show empty state if no filter is active and no data
  if (!summary || (jobs.length === 0 && !hasActiveFilters)) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Results
        </Typography>
        <EmptyState
          title="No Evaluation Results"
          description="Start an evaluation to see results here."
          actionLabel="Go to Test Runner"
          onAction={() => (window.location.href = '/test')}
        />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Evaluation Jobs
      </Typography>
      <Typography variant="body1" color="text.secondary" gutterBottom>
        View the latest evaluation jobs. Click &quot;View Cases&quot; to inspect tokens, scores, and criteria.
      </Typography>

      {/* Filters Section */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box display="flex" alignItems="center" gap={1} mb={2}>
          <FilterListIcon />
          <Typography variant="h6">Filters</Typography>
          {hasActiveFilters && (
            <Button
              size="small"
              startIcon={<ClearIcon />}
              onClick={handleClearFilters}
              sx={{ ml: 'auto' }}
            >
              Clear Filters
            </Button>
          )}
        </Box>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <TextField
              fullWidth
              label="Job ID"
              value={filters.job_id}
              onChange={(e) => handleFilterChange('job_id', e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void fetchData();
                }
              }}
              placeholder="Enter job ID"
              size="small"
            />
          </Grid>
        </Grid>
      </Paper>

      <Grid container spacing={3} sx={{ mt: 2, mb: 4 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <SummaryCard
            title={hasActiveFilters ? "Filtered Cases" : "Latest Job Cases"}
            value={summary.total_evaluations}
            subtitle={hasActiveFilters ? "Cases matching filters" : "Cases in most recent evaluation"}
            icon={<Assessment />}
            color="primary"
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <SummaryCard
            title={hasActiveFilters ? "Filtered Score" : "Latest Job Score"}
            value={`${summary.average_score.toFixed(1)}%`}
            subtitle={hasActiveFilters ? "Average score of filtered results" : "Average score of latest job"}
            icon={<TrendingUp />}
            color="success"
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <SummaryCard
            title="Flagged Cases"
            value={summary.cases_flagged_for_review}
            subtitle="Need review (score < 75%)"
            icon={<Warning />}
            color="warning"
          />
        </Grid>
      </Grid>

      <DataTable columns={columns} rows={jobs} onRowClick={handleViewDetails} />

      <Dialog open={detailsOpen} onClose={handleCloseDetails} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">
              Job Cases: {selectedJob?.job_id ?? '—'}
            </Typography>
            <IconButton onClick={handleCloseDetails} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {detailsLoading && (
            <Box py={4} display="flex" justifyContent="center">
              <CircularProgress />
            </Box>
          )}

          {detailsError && <Alert severity="error">{detailsError}</Alert>}

          {!detailsLoading && !detailsError && selectedJobDetails && (
            <Box>
              {selectedJobDetails.detailed_results.length > 0 ? (
                <Box>
                  <Box
                    mb={3}
                    p={2}
                    sx={{
                      bgcolor: 'background.paper',
                      borderRadius: 1,
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Typography variant="h6" gutterBottom>
                      Job Summary
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid size={{ xs: 6, sm: 3 }}>
                        <Typography variant="body2" color="text.secondary">
                          Total Cases
                        </Typography>
                        <Typography variant="h6">
                          {selectedJobDetails.summary.total_evaluations}
                        </Typography>
                      </Grid>
                      <Grid size={{ xs: 6, sm: 3 }}>
                        <Typography variant="body2" color="text.secondary">
                          Average Score
                        </Typography>
                        <Typography variant="h6" color="primary.main">
                          {selectedJobDetails.summary.average_score.toFixed(1)}%
                        </Typography>
                      </Grid>
                      <Grid size={{ xs: 6, sm: 3 }}>
                        <Typography variant="body2" color="text.secondary">
                          Flagged Cases
                        </Typography>
                        <Typography variant="h6" color="error.main">
                          {selectedJobDetails.summary.cases_flagged_for_review}
                        </Typography>
                      </Grid>
                      <Grid size={{ xs: 6, sm: 3 }}>
                        <Typography variant="body2" color="text.secondary">
                          Model
                        </Typography>
                        <Typography variant="h6">
                          {selectedJobDetails.summary.model}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Box>

                  <Divider sx={{ my: 3 }} />

                  <Typography variant="h6" gutterBottom>
                    All Cases in This Job ({selectedJobDetails.detailed_results.length} Cases)
                  </Typography>

                  <Box>
                    {selectedJobDetails.detailed_results.map((caseResult) => {
                      const timestamp = caseResult.created_at
                        ? new Date(caseResult.created_at).toLocaleString()
                        : '—';

                      return (
                        <Box
                          key={`${caseResult.case_id}-${caseResult.created_at}`}
                          mb={2}
                          p={2}
                          sx={{
                            bgcolor: 'background.paper',
                            borderRadius: 1,
                            border: '1px solid',
                            borderColor: 'divider',
                          }}
                        >
                          <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
                            <Box>
                              <Typography variant="subtitle2" fontWeight="bold">
                                Case ID: {caseResult.case_id}
                              </Typography>
                              <Typography variant="body2" color="text.secondary">
                                {timestamp}
                              </Typography>
                            </Box>
                            <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
                              <Typography
                                variant="h6"
                                color={caseResult.total_score >= 75 ? 'success.main' : 'warning.main'}
                              >
                                {caseResult.total_score.toFixed(1)}%
                              </Typography>
                              {caseResult.flagged_for_review && <StatusBadge status="flagged" size="small" />}
                              {caseResult.trace_id && (
                                <Box display="flex" alignItems="center" gap={1} sx={{ ml: 1 }}>
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    startIcon={<TimelineIcon />}
                                    endIcon={<OpenInNewIcon />}
                                    onClick={async () => {
                                      try {
                                        const response = await apiService.getTraceUrl(caseResult.trace_id!);
                                        if (response?.urls?.grafana) {
                                          window.open(response.urls.grafana, '_blank');
                                        }
                                      } catch (err) {
                                        console.error('Failed to open trace:', err);
                                      }
                                    }}
                                  >
                                    View Trace
                                  </Button>
                                  <Box
                                    display="flex"
                                    alignItems="center"
                                    gap={0.5}
                                    sx={{
                                      px: 1,
                                      py: 0.5,
                                      bgcolor: 'background.paper',
                                      border: '1px solid',
                                      borderColor: 'divider',
                                      borderRadius: 1,
                                      fontSize: '0.75rem',
                                    }}
                                  >
                                    <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
                                      Trace ID: {caseResult.trace_id.substring(0, 8)}...
                                    </Typography>
                                    <IconButton
                                      size="small"
                                      onClick={() => {
                                        navigator.clipboard.writeText(caseResult.trace_id!);
                                        // You could add a toast notification here if you have one
                                      }}
                                      sx={{ p: 0.5 }}
                                      title="Copy trace ID"
                                    >
                                      <ContentCopyIcon fontSize="small" />
                                    </IconButton>
                                  </Box>
                                </Box>
                              )}
                            </Box>
                          </Box>

                          <Grid container spacing={2} mb={2}>
                            <Grid size={{ xs: 12, sm: 4 }}>
                              <Typography variant="caption" color="text.secondary">
                                Prompt Tokens
                              </Typography>
                              <Typography variant="body2">
                                {caseResult.prompt_tokens ?? '—'}
                              </Typography>
                            </Grid>
                            <Grid size={{ xs: 12, sm: 4 }}>
                              <Typography variant="caption" color="text.secondary">
                                Completion Tokens
                              </Typography>
                              <Typography variant="body2">
                                {caseResult.completion_tokens ?? '—'}
                              </Typography>
                            </Grid>
                            <Grid size={{ xs: 12, sm: 4 }}>
                              <Typography variant="caption" color="text.secondary">
                                Total Tokens
                              </Typography>
                              <Typography variant="body2">
                                {caseResult.total_tokens ?? '—'}
                              </Typography>
                            </Grid>
                          </Grid>

                          {selectedJobDetails?.criteria_schema && selectedJobDetails.criteria_schema.length > 0 && (
                            <Box mt={2}>
                              <Typography variant="body2" color="text.secondary" gutterBottom>
                                Criteria Breakdown ({selectedJobDetails.criteria_schema.length} Criteria):
                              </Typography>
                              <Box maxHeight={200} sx={{ overflowY: 'auto' }}>
                                {selectedJobDetails.criteria_schema.map((criterion) => {
                                  // Debug: Print the raw criteria_scores object for this case
                                  // to verify the frontend receives actual scores keyed by criterion id
                                  console.log('Criteria scores for case:', caseResult.case_id, caseResult.criteria_scores);
                                  // Lookup score using criterion ID as key
                                  const criterionKey = String(criterion.id);
                                  const scoreData = caseResult.criteria_scores?.[criterionKey];
                                  
                                  // Handle both new format {score: X, id: Y} and old format (just a number)
                                  let value: number = 0;
                                  if (scoreData !== undefined && scoreData !== null) {
                                    if (typeof scoreData === 'object' && 'score' in scoreData) {
                                      // New format with ID
                                      const scoreObj = scoreData as { score: number; id?: number };
                                      value = typeof scoreObj.score === 'number' ? scoreObj.score : 0;
                                    } else if (typeof scoreData === 'number') {
                                      // Old format (backward compatibility) - just a number
                                      value = scoreData;
                                    }
                                  }

                                  const maxScore = criterion.max_score;
                                  const percentage = maxScore > 0 ? (value / maxScore) * 100 : 0;

                                  return (
                                    <Box
                                      key={criterion.id}
                                      mb={1}
                                      p={1}
                                      sx={{ bgcolor: 'background.default', borderRadius: 1 }}
                                    >
                                      <Box display="flex" justifyContent="space-between" alignItems="center">
                                        <Typography variant="caption" sx={{ flex: 1, mr: 1 }}>
                                          {criterion.name}
                                        </Typography>
                                        <Typography variant="caption" fontWeight="bold">
                                          {value}/{maxScore}
                                        </Typography>
                                      </Box>
                                      <LinearProgress
                                        variant="determinate"
                                        value={percentage}
                                        color={
                                          percentage >= 75 ? 'success' : percentage >= 50 ? 'warning' : 'error'
                                        }
                                        sx={{ height: 3, borderRadius: 1, mt: 0.5 }}
                                      />
                                    </Box>
                                  );
                                })}
                              </Box>
                            </Box>
                          )}
                          {/* Fallback for old data without schema */}
                          {(!selectedJobDetails?.criteria_schema || selectedJobDetails.criteria_schema.length === 0) && 
                           caseResult.criteria_scores && Object.keys(caseResult.criteria_scores).length > 0 && (
                            <Box mt={2}>
                              <Typography variant="body2" color="text.secondary" gutterBottom>
                                Criteria Breakdown ({Object.keys(caseResult.criteria_scores).length} Criteria):
                              </Typography>
                              <Typography variant="body2" color="warning.main">
                                Schema not available. Please run a new evaluation to see detailed criteria information.
                              </Typography>
                            </Box>
                          )}
                        </Box>
                      );
                    })}
                  </Box>
                </Box>
              ) : (
                <Box p={3} textAlign="center">
                  <Typography variant="body1" color="text.secondary">
                    No case data available for this job.
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Job ID: {selectedJob?.job_id}
                  </Typography>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleDownloadResults}
            variant="outlined"
            startIcon={<DownloadIcon />}
            disabled={!selectedJobDetails || detailsLoading}
          >
            Download Results (JSON)
          </Button>
          <Button onClick={handleCloseDetails} variant="contained">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

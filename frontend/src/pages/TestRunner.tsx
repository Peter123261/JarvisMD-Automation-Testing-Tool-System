/**
 * Test Runner Page
 * Interface for starting new evaluation jobs
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  Chip,
  LinearProgress,
  Fade,
  MenuItem,
} from '@mui/material';
import {
  PlayArrow as PlayArrowIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  HourglassEmpty as HourglassIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import { apiService } from '../services/api';

type EvaluationStatus = 'idle' | 'starting' | 'running' | 'completed' | 'failed' | 'cancelled';

export default function TestRunner() {
  const [benchmarkName, setBenchmarkName] = useState('');
  const [numCases, setNumCases] = useState(0);
  const [numCasesInput, setNumCasesInput] = useState<string>('0');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<any>(null);
  const [evaluationStatus, setEvaluationStatus] = useState<EvaluationStatus>('idle');
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [progressInterval, setProgressInterval] = useState<ReturnType<typeof setInterval> | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancellationNotice, setCancellationNotice] = useState<string | null>(null);
  const [benchmarkOptions, setBenchmarkOptions] = useState<string[]>([]);

  // Monitor evaluation progress
  const monitorEvaluation = async (jobId: string) => {
    try {
      const status = await apiService.getEvaluationStatus(jobId);
      
      if (status.status === 'completed') {
        setEvaluationStatus('completed');
        setProgress(100);
        setSuccess({
          job_id: jobId,
          status: 'completed',
          total_cases: status.total_cases,
          successful_cases: status.successful_cases,
          failed_cases: status.failed_cases,
          average_score: status.average_score,
        });
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        if (progressInterval) {
          clearInterval(progressInterval);
          setProgressInterval(null);
        }
        setCancelLoading(false);
      } else if (status.status === 'cancelled') {
        setEvaluationStatus('cancelled');
        setProgress(0);
        setCancellationNotice('Evaluation was cancelled.');
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        if (progressInterval) {
          clearInterval(progressInterval);
          setProgressInterval(null);
        }
        setCancelLoading(false);
      } else if (status.status === 'failed') {
        setEvaluationStatus('failed');
        setError('Evaluation failed to complete');
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        if (progressInterval) {
          clearInterval(progressInterval);
          setProgressInterval(null);
        }
      } else if (status.status === 'running') {
        setEvaluationStatus('running');
        // Calculate progress based on completed cases
        if (status.total_cases > 0) {
          const completedCases = (status.successful_cases || 0) + (status.failed_cases || 0);
          const progressPercent = (completedCases / status.total_cases) * 100;
          setProgress(progressPercent);
        } else {
          // Simple progress fallback
          setProgress(prev => Math.min(prev + 10, 90));
        }
      }
    } catch (err) {
      console.error('Error monitoring evaluation:', err);
    }
  };

  // Load available benchmarks for dropdown on mount
  useEffect(() => {
    (async () => {
      try {
        const resp = await apiService.getBenchmarks();
        const ids: string[] = Array.isArray(resp?.benchmarks)
          ? resp.benchmarks.map((b: any) => b?.id).filter((v: any) => typeof v === 'string')
          : [];
        if (ids.length) {
          setBenchmarkOptions(ids);
          // Auto-select first benchmark if none selected yet
          if (!benchmarkName && ids.length > 0) {
            setBenchmarkName(ids[0]);
          }
        }
      } catch (e) {
        // Silently ignore; keep manual entry available
        // eslint-disable-next-line no-console
        console.warn('Failed to load benchmark list:', e);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run once on mount

  // Cleanup intervals on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (progressInterval) {
        clearInterval(progressInterval);
      }
    };
  }, [progressInterval]);

  // Reset form for new evaluation
  const resetForm = () => {
    setEvaluationStatus('idle');
    setCurrentJobId(null);
    setProgress(0);
    setError(null);
    setSuccess(null);
    setNumCasesInput('0');
    setNumCases(0);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (progressInterval) {
      clearInterval(progressInterval);
      setProgressInterval(null);
    }
    setCancelLoading(false);
    setCancellationNotice(null);
  };

  const handleStartEvaluation = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);
      setCancellationNotice(null);
      setCancelLoading(false);
      setEvaluationStatus('starting');
      setProgress(0);

      if (!benchmarkName) {
        throw new Error('Benchmark name is required');
      }
      // Convert string input to number for validation
      const casesToEvaluate = parseInt(numCasesInput, 10) || 0;
      if (casesToEvaluate < 1 || casesToEvaluate > 1000) {
        throw new Error('Number of cases must be between 1 and 1000');
      }

      const response = await apiService.startEvaluation({
        benchmark_name: benchmarkName,
        num_cases: casesToEvaluate,
      });

      setCurrentJobId(response.job_id);
      setEvaluationStatus('running');
      setProgress(0);
      
      // Start monitoring the evaluation
      intervalRef.current = setInterval(() => {
        monitorEvaluation(response.job_id);
      }, 5000); // Check every 5 seconds for faster completion detection

      console.log('Evaluation started:', response);
    } catch (err: any) {
      console.error('Failed to start evaluation:', err);
      setError(err.response?.data?.detail || err.message);
      setEvaluationStatus('failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCancelEvaluation = async () => {
    if (!currentJobId) return;
    try {
      setCancelLoading(true);
      setError(null);
      setCancellationNotice(null);
      setSuccess(null);
      await apiService.cancelEvaluation(currentJobId);
      setEvaluationStatus('cancelled');
      setProgress(0);
      setCancellationNotice('Evaluation cancelled successfully.');
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (progressInterval) {
        clearInterval(progressInterval);
        setProgressInterval(null);
      }
    } catch (err: any) {
      console.error('Failed to cancel evaluation:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to cancel evaluation');
    } finally {
      setCancelLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Test Runner
      </Typography>
      <Typography variant="body1" color="text.secondary" gutterBottom>
        Start a new evaluation job
      </Typography>

      {/* Status Indicators */}
      {evaluationStatus !== 'idle' && (
        <Fade in={true}>
          <Card sx={{ mt: 2, mb: 2 }}>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                <Box display="flex" alignItems="center" gap={2}>
                  {evaluationStatus === 'starting' && (
                    <>
                      <CircularProgress size={24} />
                      <Typography variant="h6">Starting Evaluation...</Typography>
                    </>
                  )}
                  {evaluationStatus === 'running' && (
                    <>
                      <HourglassIcon color="primary" />
                      <Typography variant="h6">Evaluation Running...</Typography>
                    </>
                  )}
                  {evaluationStatus === 'completed' && (
                    <>
                      <CheckCircleIcon color="success" />
                      <Typography variant="h6" color="success.main">Evaluation Completed Successfully!</Typography>
                    </>
                  )}
                  {evaluationStatus === 'failed' && (
                    <>
                      <ErrorIcon color="error" />
                      <Typography variant="h6" color="error.main">Evaluation Failed</Typography>
                    </>
                  )}
              {evaluationStatus === 'cancelled' && (
                <>
                  <CancelIcon color="warning" />
                  <Typography variant="h6" color="warning.main">Evaluation Cancelled</Typography>
                </>
              )}
                </Box>
                <Chip
                  label={evaluationStatus.toUpperCase()}
                  color={
                    evaluationStatus === 'completed' ? 'success' :
                    evaluationStatus === 'failed' ? 'error' :
                evaluationStatus === 'running' ? 'primary' :
                evaluationStatus === 'cancelled' ? 'warning' : 'default'
                  }
                  variant="outlined"
                />
              </Box>
              
              {currentJobId && (
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Job ID: {currentJobId}
                </Typography>
              )}
              
              {(evaluationStatus === 'running' || evaluationStatus === 'starting') && (
                <Box>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2">Progress</Typography>
                    <Typography variant="body2">{Math.round(progress)}%</Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={progress} 
                    sx={{ height: 8, borderRadius: 4 }}
                  />
                  <Box display="flex" justifyContent="flex-end" mt={2}>
                    <Button
                      variant="outlined"
                      color="warning"
                      startIcon={cancelLoading ? <CircularProgress size={20} /> : <CancelIcon />}
                      onClick={handleCancelEvaluation}
                      disabled={cancelLoading}
                    >
                      {cancelLoading ? 'Cancelling...' : 'Cancel Evaluation'}
                    </Button>
                  </Box>
                </Box>
              )}
              
              {evaluationStatus === 'completed' && success && (
                <Box mt={2}>
                  <Button
                    variant="outlined"
                    startIcon={<PlayArrowIcon />}
                    onClick={resetForm}
                    size="small"
                  >
                    Start New Evaluation
                  </Button>
                </Box>
              )}
              {evaluationStatus === 'cancelled' && (
                <Box mt={2}>
                  <Button
                    variant="outlined"
                    startIcon={<PlayArrowIcon />}
                    onClick={resetForm}
                    size="small"
                  >
                    Start New Evaluation
                  </Button>
                </Box>
              )}
            </CardContent>
          </Card>
        </Fade>
      )}

      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}
      {cancellationNotice && (
        <Alert severity="info" sx={{ mt: 2 }}>
          {cancellationNotice}
        </Alert>
      )}

      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="h6" gutterBottom>
          Evaluation Configuration
        </Typography>

        <Box component="form" onSubmit={handleStartEvaluation} sx={{ mt: 2 }}>
          <TextField
            select={benchmarkOptions.length > 0}
            fullWidth
            label="Benchmark Name"
            value={benchmarkName}
            onChange={(e) => setBenchmarkName(e.target.value)}
            helperText={
              benchmarkOptions.length > 0
                ? 'Select a prompt'
                : 'Enter the benchmark name manually (e.g., appraise_v2)'
            }
            sx={{ mb: 3 }}
            disabled={loading}
          >
            {benchmarkOptions.map((opt) => (
              <MenuItem key={opt} value={opt}>
                {opt}
              </MenuItem>
            ))}
          </TextField>

          <TextField
            fullWidth
            type="number"
            label="Number of Cases"
            value={numCasesInput}
            onFocus={(e) => {
              // Clear 0 when user starts typing - select all text
              if (numCasesInput === '0') {
                e.target.select();
              }
            }}
            onChange={(e) => {
              const value = e.target.value;
              // Update the string input value
              setNumCasesInput(value);
              // Also update the numeric value for validation
              const parsed = parseInt(value, 10);
              if (!isNaN(parsed)) {
                setNumCases(parsed);
              } else if (value === '' || value === '-') {
                setNumCases(0);
              }
            }}
            onBlur={(e) => {
              // If empty after blur, set back to 0
              const value = e.target.value;
              if (value === '' || value === '0' || parseInt(value, 10) === 0) {
                setNumCasesInput('0');
                setNumCases(0);
              } else {
                // Ensure the input shows the parsed number
                const parsed = parseInt(value, 10);
                if (!isNaN(parsed)) {
                  setNumCasesInput(parsed.toString());
                  setNumCases(parsed);
                }
              }
            }}
            helperText="Number of medical cases to evaluate (1-1000)"
            inputProps={{ min: 1, max: 1000 }}
            sx={{ mb: 3 }}
            disabled={loading}
          />

          <Button
            type="submit"
            variant="contained"
            size="large"
            startIcon={loading ? <CircularProgress size={20} /> : <PlayArrowIcon />}
            disabled={loading}
          >
            {loading ? 'Starting Evaluation...' : 'Start Evaluation'}
          </Button>
        </Box>
      </Paper>

      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            ��� How It Works
          </Typography>
          <Typography variant="body2" paragraph>
            1. <strong>Select Benchmark:</strong> Choose the evaluation framework
          </Typography>
          <Typography variant="body2" paragraph>
            2. <strong>Set Case Count:</strong> Specify how many cases to evaluate
          </Typography>
          <Typography variant="body2" paragraph>
            3. <strong>Start Evaluation:</strong> Submit the form to begin
          </Typography>
          <Alert severity="info" sx={{ mt: 2 }}>
            Evaluations run asynchronously in the background. Monitor progress via Flower dashboard.
          </Alert>
        </CardContent>
      </Card>
    </Box>
  );
}

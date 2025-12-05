/**
 * API Service for JarvisMD Medical Automation Tool
 * Handles all communication with the backend API
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8010/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const API_ENDPOINTS = {
  HEALTH: '/health',
  CASE_COUNT: '/cases/count',
  BENCHMARKS: '/benchmarks',
  START_TEST: '/test/start',
  TEST_STATUS: (jobId: string) => `/test/${jobId}/status`,
  TEST_RESULTS: (jobId: string) => `/test/${jobId}/results`,
  CANCEL_TEST: (jobId: string) => `/test/${jobId}/cancel`,
  RESULTS_SUMMARY: '/results/summary',
  RESULTS_RECENT_JOBS: '/results/jobs/recent',
  LOW_SCORE_ALERTS: '/results/alerts/low-scores',
  TRACE_URL: (traceId: string) => `/results/trace/${traceId}`,
  METRICS: '/metrics',
  COST_METRICS: '/metrics/cost',
  PROMETHEUS_METRICS: '/metrics/prometheus',
  LATEST_JOB_METRICS: '/metrics/job/latest',
} as const;

export interface EvaluationRequest {
  benchmark_name: string;
  num_cases: number;
}

export interface EvaluationResponse {
  job_id: string;
  status: string;
  total_cases: number;
  benchmark: string;
  model: string;
  start_time: string;
}

export const apiService = {
  async checkHealth() {
    const response = await apiClient.get(API_ENDPOINTS.HEALTH);
    return response.data;
  },

  async getCaseCount() {
    const response = await apiClient.get(API_ENDPOINTS.CASE_COUNT);
    return response.data;
  },

  async getBenchmarks() {
    const response = await apiClient.get(API_ENDPOINTS.BENCHMARKS);
    return response.data;
  },

  async startEvaluation(request: EvaluationRequest) {
    const response = await apiClient.post(API_ENDPOINTS.START_TEST, request);
    return response.data as EvaluationResponse;
  },

  async getEvaluationStatus(jobId: string) {
    const response = await apiClient.get(API_ENDPOINTS.TEST_STATUS(jobId));
    return response.data;
  },

  async getEvaluationResults(jobId: string) {
    const response = await apiClient.get(API_ENDPOINTS.TEST_RESULTS(jobId));
    return response.data;
  },

  async cancelEvaluation(jobId: string) {
    const response = await apiClient.post(API_ENDPOINTS.CANCEL_TEST(jobId));
    return response.data;
  },

  // Get all evaluation results summary
  async getResultsSummary(filters?: {
    job_id?: string;
    start_date?: string;
    end_date?: string;
    benchmark?: string;
  }) {
    const response = await apiClient.get(API_ENDPOINTS.RESULTS_SUMMARY, {
      params: filters,
    });
    return response.data;
  },

  async getRecentJobs(limit = 10, benchmark?: string) {
    const response = await apiClient.get(API_ENDPOINTS.RESULTS_RECENT_JOBS, {
      params: { limit, ...(benchmark && { benchmark }) },
    });
    return response.data;
  },

  // Get flagged cases (low scores)
  async getLowScoreAlerts() {
    const response = await apiClient.get(API_ENDPOINTS.LOW_SCORE_ALERTS);
    return response.data;
  },

  async getMetrics() {
    const response = await apiClient.get(API_ENDPOINTS.METRICS);
    return response.data;
  },

  async getLatestJobMetrics(jobId?: string) {
    const params = jobId ? { job_id: jobId } : undefined;
    const response = await apiClient.get(API_ENDPOINTS.LATEST_JOB_METRICS, { params });
    return response.data;
  },

  async getTraceUrl(traceId: string) {
    const response = await apiClient.get(API_ENDPOINTS.TRACE_URL(traceId));
    return response.data;
  },
};

export default apiService;

/**
 * API Client - Axios configuration for backend communication
 */

import axios from 'axios';
import type { AxiosInstance, AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
const NETWORK_COOLDOWN_MS = 10000;

let networkCooldownUntil = 0;

const isNetworkError = (error: AxiosError): boolean => {
  return !error.response && (error.code === 'ERR_NETWORK' || error.message === 'Network Error');
};

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - Add auth token
apiClient.interceptors.request.use(
  (config) => {
    if (Date.now() < networkCooldownUntil) {
      const waitSeconds = Math.ceil((networkCooldownUntil - Date.now()) / 1000);
      return Promise.reject(
        new axios.AxiosError(
          `Backend temporarily unavailable. Retrying in ${waitSeconds}s.`,
          'ERR_NETWORK_COOLDOWN',
          config
        )
      );
    }

    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle errors globally
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (isNetworkError(error)) {
      networkCooldownUntil = Date.now() + NETWORK_COOLDOWN_MS;
    }

    if (error.response?.status === 401) {
      // Unauthorized - redirect to login
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// API Methods
export const api = {
  // Upload & Processing
  upload: {
    single: (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return apiClient.post('/upload/single', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    },
    batch: (files: File[]) => {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));
      return apiClient.post('/upload/batch', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    },
  },

  // Verification
  verification: {
    list: (params: any) => apiClient.get('/verification/list', { params }),
    getRecord: (id: number) => apiClient.get(`/verification/${id}`),
    correct: (id: number, data: any) => apiClient.post(`/verification/${id}/correct`, data),
    getStats: () => apiClient.get('/verification/stats/summary'),
  },

  // Streaming
  streaming: {
    listCameras: () => apiClient.get('/streaming/cameras'),
    createCamera: (data: any) => apiClient.post('/streaming/cameras', data),
    updateCamera: (id: number, data: any) => apiClient.put(`/streaming/cameras/${id}`, data),
    deleteCamera: (id: number) => apiClient.delete(`/streaming/cameras/${id}`),
    startStream: (id: number) => apiClient.post(`/streaming/cameras/${id}/start`),
    stopStream: (id: number) => apiClient.post(`/streaming/cameras/${id}/stop`),
    getActiveStreams: () => apiClient.get('/streaming/streams/active'),
  },

  // Master Data
  masterData: {
    getProvinces: () => apiClient.get('/master-data/provinces'),
    getVehicles: (params?: any) => apiClient.get('/master-data/vehicles', { params }),
    searchVehicle: (plateNumber: string) => 
      apiClient.get(`/master-data/vehicles/search?plate_number=${plateNumber}`),
  },

  // Analytics
  analytics: {
    getDashboard: () => apiClient.get('/analytics/dashboard/summary'),
    getDailyTrend: (days: number) => apiClient.get(`/analytics/dashboard/daily-trend?days=${days}`),
    getTopProvinces: (limit: number) => 
      apiClient.get(`/analytics/dashboard/top-provinces?limit=${limit}`),
  },

  // Export
  export: {
    excel: (params?: any) =>
      apiClient.get('/export/excel', {
        params,
        responseType: 'blob',
      }),
    pdf: (params?: any) =>
      apiClient.get('/export/pdf', {
        params,
        responseType: 'blob',
      }),
  },

  // Auth
  auth: {
    login: (username: string, password: string) => {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);
      return apiClient.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
    },
    getCurrentUser: () => apiClient.get('/auth/me'),
  },
};

export default apiClient;

import axios, { AxiosError, AxiosInstance, AxiosResponse } from 'axios';
import config from '../config/env.config';

const axiosInstance: AxiosInstance = axios.create({
  baseURL: config.apiBaseUrl,
  timeout: 120000, // Increase timeout to 120 seconds for long-running agent operations
  headers: {
    'Content-Type': 'application/json',
  },
});

axiosInstance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  (error: AxiosError) => {
    let errorMessage = 'An unexpected error occurred';
    
    if (error.response) {
      // Server responded with error status
      const responseData = error.response.data as any;
      
      // Extract error message from response
      if (responseData?.detail?.message) {
        errorMessage = responseData.detail.message;
      } else if (responseData?.message) {
        errorMessage = responseData.message;
      } else if (responseData?.detail) {
        errorMessage = typeof responseData.detail === 'string' 
          ? responseData.detail 
          : JSON.stringify(responseData.detail);
      }
      
      switch (error.response.status) {
        case 400:
          console.error('Bad Request:', errorMessage);
          break;
        case 401:
          console.error('Unauthorized');
          localStorage.removeItem('token');
          // Don't redirect on estimate page
          if (!window.location.pathname.includes('/estimate')) {
            window.location.href = '/login';
          }
          break;
        case 403:
          console.error('Access forbidden:', errorMessage);
          break;
        case 404:
          console.error('Resource not found:', errorMessage);
          break;
        case 422:
          console.error('Validation error:', errorMessage);
          break;
        case 500:
          console.error('Internal server error:', errorMessage);
          break;
        case 503:
          console.error('Service unavailable:', errorMessage);
          break;
        default:
          console.error(`Error ${error.response.status}:`, errorMessage);
      }
      
      // Attach formatted error message to error object
      (error as any).userMessage = errorMessage;
      
    } else if (error.request) {
      // Request made but no response received
      if (error.code === 'ECONNABORTED') {
        errorMessage = 'Request timeout - The operation took too long. Please try again.';
      } else if (error.code === 'ERR_NETWORK') {
        errorMessage = 'Network error - Unable to connect to server. Please check your connection.';
      } else {
        errorMessage = 'Network error - No response received from server';
      }
      console.error('Network error:', errorMessage);
      (error as any).userMessage = errorMessage;
    } else {
      // Error in request setup
      errorMessage = error.message || 'Error setting up request';
      console.error('Request error:', errorMessage);
      (error as any).userMessage = errorMessage;
    }
    
    return Promise.reject(error);
  }
);

export { axiosInstance };
export default axiosInstance;

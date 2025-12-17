import axios from '../utils/axios';

export interface User {
  id: string;
  name: string;
  email: string;
}

export interface Alert {
  id: string;
  type: string;
  message: string;
  timestamp: string;
}

export const userService = {
  getCurrentUser: async (): Promise<User> => {
    const response = await axios.get<User>('/users/me');
    return response.data;
  },

  updateUser: async (userId: string, data: Partial<User>): Promise<User> => {
    const response = await axios.put<User>(`/users/${userId}`, data);
    return response.data;
  },
};

// Alert API calls
export const alertService = {
  getAlerts: async (): Promise<Alert[]> => {
    const response = await axios.get<Alert[]>('/alerts');
    return response.data;
  },

  getAlertById: async (alertId: string): Promise<Alert> => {
    const response = await axios.get<Alert>(`/alerts/${alertId}`);
    return response.data;
  },

  createAlert: async (data: Omit<Alert, 'id'>): Promise<Alert> => {
    const response = await axios.post<Alert>('/alerts', data);
    return response.data;
  },

  deleteAlert: async (alertId: string): Promise<void> => {
    await axios.delete(`/alerts/${alertId}`);
  },
};

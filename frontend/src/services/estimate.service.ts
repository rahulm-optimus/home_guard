
/**
 * Estimate Service - API calls for cost estimation
 */
import { axiosInstance } from '../utils/axios';
import {
  EstimateQueryInput,
  EstimateResponse,
  SaveItemsRequest,
  SaveItemsResponse,
  GetItemsResponse,
  UpdateItemRequest,
  UpdateItemResponse
} from '../types/api.types';

export const estimateService = {
  /**
   * Get cost estimates for items
   */
  async getEstimate(data: EstimateQueryInput): Promise<EstimateResponse> {
    // const response = await axiosInstance.post<EstimateResponse>('/api/v1/estimate', data);
    const response = await axiosInstance.post<EstimateResponse>('/api/v1/cost-estimate', data);
    return response.data;
  },

  /**
   * Save items to Cosmos DB
   */
  async saveItems(data: SaveItemsRequest): Promise<SaveItemsResponse> {
    const response = await axiosInstance.post<SaveItemsResponse>('/api/v1/save-items', data);
    return response.data;
  },

  /**
   * Get all saved items with pagination
   */
  async getItems(offset: number = 0, limit: number = 10): Promise<GetItemsResponse> {
    const response = await axiosInstance.get<GetItemsResponse>('/api/v1/items', {
      params: { offset, limit },
    });
    return response.data;
  },

  /**
   * Search items by message with pagination
   */
  async searchItems(searchQuery: string, offset: number = 0, limit: number = 10): Promise<GetItemsResponse> {
    const response = await axiosInstance.get<GetItemsResponse>('/api/v1/search-items', {
      params: { search_query: searchQuery, offset, limit },
    });
    return response.data;
  },

  /**
   * Update an existing item in Cosmos DB
   */
  async updateItem(itemId: string, zipcode: string, data: UpdateItemRequest): Promise<UpdateItemResponse> {
    const response = await axiosInstance.put<UpdateItemResponse>(
      `/api/v1/update-item/${itemId}`,
      data,
      { params: { zipcode } }
    );
    return response.data;
  },

  async getClusters(offset: number = 0, limit: number = 10, search: string = ''): Promise<GetItemsResponse> {
    const response = await axiosInstance.get<GetItemsResponse>('/api/v1/clusters', {
      params: { offset, limit, search },
    });
    return response.data;
  },

  /**
   * Create a new cluster
   */
  async createCluster(data: { name: string; zipcodes: string[]; description?: string }): Promise<any> {
    const response = await axiosInstance.post('/api/v1/clusters', data);
    return response.data;
  },

  /**
   * Update an existing cluster
   */
  async updateCluster(clusterId: string, data: { name?: string; zipcodes?: string[]; description?: string }): Promise<any> {
    const response = await axiosInstance.put(`/api/v1/clusters/${clusterId}`, data);
    return response.data;
  },

  /**
   * Check if a cluster name already exists
   */
  async checkClusterName(name: string): Promise<{ exists: boolean; cluster_id?: string; name?: string; zipcodes?: string[]; zipcode_count?: number }> {
    const response = await axiosInstance.get('/api/v1/clusters/check-name', {
      params: { name },
    });
    return response.data;
  },
};

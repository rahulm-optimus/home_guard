
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
};

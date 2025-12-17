/**
 * API Types for HomeGuard Application
 */

// Estimate Types
export interface EstimateModel {
  min: number;
  max: number;
}

export interface ItemDetail {
  description: string;
  subcategory: string;
  estimate: EstimateModel;
  note: string;
}

export interface EstimateQueryInput {
  query: string[];
  category: string;
  zipcode: string;
  address: string;
  username: string;
}

export interface EstimateItemResponse {
  category: string;
  items: ItemDetail[];
  dateofcreation: string;
  zipcode: string;
  address: string;
  username: string;
}

export interface EstimateResponse {
  status: string;
  status_code: number;
  message: string[];
  error: string[];
  data: EstimateItemResponse;
}

// Save Types
export interface SaveItemInput {
  id: string;
  category: string;
  items: ItemDetail[];
  dateofcreation: string;
  zipcode: string;
  address: string;
  username: string;
  status: string;
}

export interface SaveItemsRequest {
  items: SaveItemInput[];
}

export interface SaveItemsResponse {
  status: string;
  status_code: number;
  message: string;
  data: {
    total_items: number;
    saved_count: number;
    failed_count: number;
    saved_items: Array<{
      id: string;
      status: string;
    }>;
  };
}

// Get Items Types
export interface GetItemsResponse {
  status: string;
  status_code: number;
  message: string;
  data: {
    items: SaveItemInput[];
    total_count: number;
    returned_count: number;
    offset: number;
    limit: number;
  };
}

// Form Types
export interface EstimationFormData {
  items: string[];
  category: string;
  zipcode: string;
  address: string;
  username: string;
}

export interface EditableItem extends ItemDetail {
  id: string;
}

import azure.functions as func
import logging

# Suppress verbose Azure SDK logs
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.cosmos").setLevel(logging.WARNING)
logging.getLogger("azure.core").setLevel(logging.WARNING)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# /save-items (POST)
import os
import json
from pydantic import ValidationError

from schemas.requests import (
    SaveCostEstimatesRequest,
    SaveCostEstimatesResponse,
    GetItemsResponse,
    UpdateCostEstimateRequest,
    UpdateCostEstimateResponse
)
from services.cosmos_db_service import CosmosDBService

@app.route(route="v1/save-items", methods=["POST"])
def save_flat_items(req: func.HttpRequest) -> func.HttpResponse:
    try:
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid JSON in request body"}),
                status_code=400,
                mimetype="application/json"
            )

        try:
            request_model = SaveCostEstimatesRequest(**req_body)
        except ValidationError as ve:
            return func.HttpResponse(
                ve.json(),
                status_code=422,
                mimetype="application/json"
            )

        cosmos_service = CosmosDBService()
        items = [item.dict() for item in request_model.items]
        result = cosmos_service.save_flat_items(items)

        response = SaveCostEstimatesResponse(
            status="success" if result["failed_count"] == 0 else "partial_success",
            saved_count=result["saved_count"]
        )
        return func.HttpResponse(
            response.json(),
            status_code=200,
            mimetype="application/json"
        )
    # No APIError handling, only generic Exception
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": "Internal server error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


# /items (GET)
@app.route(route="v1/items", methods=["GET"])
def get_items(req: func.HttpRequest) -> func.HttpResponse:
    try:
        offset = int(req.params.get("offset", 0))
        limit = int(req.params.get("limit", 10))
        cosmos_service = CosmosDBService()
        result = cosmos_service.get_all_items(offset=offset, limit=limit)
        message = f"Retrieved {result['returned_count']} items out of {result['total_count']} total"
        response = GetItemsResponse(
            data=result,
            status="success",
            status_code=200,
            message=message
        )
        return func.HttpResponse(
            response.json(),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": "Internal server error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


# /search-items (GET)
@app.route(route="v1/search-items", methods=["GET"])
def search_items(req: func.HttpRequest) -> func.HttpResponse:
    try:
        search_query = req.params.get("search_query")
        offset = int(req.params.get("offset", 0))
        limit = int(req.params.get("limit", 10))
        if not search_query:
            return func.HttpResponse(
                json.dumps({"error": "Missing search_query parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        cosmos_service = CosmosDBService()
        result = cosmos_service.search_items_by_message(
            search_query=search_query,
            offset=offset,
            limit=limit
        )
        message = f"Found {result['returned_count']} items matching '{search_query}' out of {result['total_count']} total"
        response = GetItemsResponse(
            data=result,
            status="success",
            status_code=200,
            message=message
        )
        return func.HttpResponse(
            response.json(),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": "Internal server error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


# /update-item/{item_id} (PUT)
@app.route(route="v1/update-item/{item_id}", methods=["PUT"])
def update_item(req: func.HttpRequest) -> func.HttpResponse:
    try:
        item_id = req.route_params.get("item_id")
        zipcode = req.params.get("zipcode")
        if not zipcode:
            return func.HttpResponse(
                json.dumps({"error": "Missing zipcode parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid JSON in request body"}),
                status_code=400,
                mimetype="application/json"
            )
        try:
            request_model = UpdateCostEstimateRequest(**req_body)
        except ValidationError as ve:
            return func.HttpResponse(
                ve.json(),
                status_code=422,
                mimetype="application/json"
            )
        cosmos_service = CosmosDBService()
        existing_item = cosmos_service.get_item(item_id, zipcode)
        if existing_item is None:
            return func.HttpResponse(
                json.dumps({"error": f"Item with id '{item_id}' not found"}),
                status_code=404,
                mimetype="application/json"
            )
        # Remove Cosmos DB system fields
        for field in ['_rid', '_self', '_etag', '_attachments', '_ts']:
            existing_item.pop(field, None)
        update_data = request_model.item.dict(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                existing_item[key] = value
        result = cosmos_service.save_flat_items([existing_item])
        if result["failed_count"] > 0:
            return func.HttpResponse(
                json.dumps({"error": "Failed to update item"}),
                status_code=500,
                mimetype="application/json"
            )
        response = UpdateCostEstimateResponse(
            status="success",
            message="Item updated successfully",
            item_id=item_id
        )
        return func.HttpResponse(
            response.json(),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": "Internal server error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
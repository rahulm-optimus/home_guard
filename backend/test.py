from app.services.history_agent_service import get_cosmos_agent_service

def test_cosmos_agent_search():
    service = get_cosmos_agent_service()
    query = f"cost of sewer repair in 94551 area"
    print(query)
    result = service.search(query)
    print("\n=== Search Result ===")
    print("Result:", result.get("extracted_json"))
if __name__ == "__main__":
    test_cosmos_agent_search()

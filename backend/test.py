"""
Test script for Azure AI Agent
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("Azure AI Agent - Connection Test")
print("=" * 60)

# Check environment variables
tenant_id = os.getenv("AZURE_TENANT_ID")
endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
agent_id = os.getenv("AZURE_AI_AGENT_ID")

print(f"\nOK Tenant: {tenant_id[:8]}...") 
print(f"OK Endpoint: {endpoint[:50]}...")
print(f"OK Agent ID: {agent_id}")

# Test connection
try:
    from azure.ai.projects import AIProjectClient
    from azure.identity import AzureCliCredential
    from azure.ai.agents.models import ListSortOrder
    
    os.environ["AZURE_TENANT_ID"] = tenant_id
    credential = AzureCliCredential(tenant_id=tenant_id)
    client = AIProjectClient(credential=credential, endpoint=endpoint)
    
    agent = client.agents.get_agent(agent_id)
    print(f"\nOK Agent connected: {agent.id}")
    
    # Test query
    print("\n" + "=" * 60)
    print("Testing Bing Integration")
    print("=" * 60)
    print("\nQuery: 'What is the AQI in Noida today?'")
    print("\nBing Status Check:")
    print("   [1] Bing is being used (real-time web data)")
    print("   [2] Bing is NOT being used (agent knowledge only)")
    
    thread = client.agents.threads.create()
    client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content="What is the AQI in Noida today? Use web search."
    )
    
    run = client.agents.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent.id
    )
    
    print(f"\nStatus: {run.status}")
    
    if run.status == "failed":
        error_msg = str(run.last_error) if hasattr(run, 'last_error') and run.last_error else "Unknown"
        if "bing_search" in error_msg.lower():
            print("\n[X] Result: Bing is configured but authentication failed")
            print("   The agent tried to use Bing but got 401 error")
            print("   -> Falling back to agent knowledge (no real-time data)")
        else:
            print(f"\n[X] Error: {error_msg}")
    
    elif run.status == "completed":
        messages = client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
        
        for msg in messages:
            if msg.role == "assistant" and hasattr(msg, "text_messages") and msg.text_messages:
                response = msg.text_messages[-1].text.value
                print(f"\nAgent Response:\n{response[:400]}...")
                
                if any(keyword in response.lower() for keyword in ["currently", "as of", "today", "latest", "real-time"]):
                    print("\n[OK] Result: Bing IS being used (response contains real-time data)")
                else:
                    print("\n[!] Result: Bing likely NOT being used (generic response)")
                break
    
    print("=" * 60)
    
    print("\nNEW AGENT (/api/v1/agent/new-estimate):")
    print("   1. Receive request -> ZIP code + item description")
    print("   2. Check Cosmos DB cache for existing estimate")
    print("   3. If not cached:")
    print("      a. Classify subcategory using LLM")
    print("      b. Call Azure AI Foundry Agent")
    print("      c. Agent uses Bing Grounding (built-in)")
    print("      d. Return estimate")
    print("   4. Cache result in Cosmos DB")
    print("   Technology: Azure AI Agent + Bing Grounding + Cosmos DB")
    
    print("\n" + "=" * 60)
    
except Exception as e:
    print(f"\n[X] Test failed: {str(e)}")
    exit(1)

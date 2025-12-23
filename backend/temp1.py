"""Test script for AZURE_CHAT_AGENT_ID"""
import os
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.agents.models import ListSortOrder

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
AZURE_AI_PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
AZURE_CHAT_AGENT_ID = os.getenv("AZURE_CHAT_AGENT_ID")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")

def test_chat_agent():
    """Test the chat agent with a simple message"""
    try:
        # Initialize credential
        credential = AzureCliCredential(tenant_id=AZURE_TENANT_ID)

        # Initialize client
        client = AIProjectClient(
            credential=credential,
            endpoint=AZURE_AI_PROJECT_ENDPOINT
        )

        print(f"Testing agent: {AZURE_CHAT_AGENT_ID}")

        # Create a thread
        thread = client.agents.threads.create()
        print(f"Created thread: {thread.id}")

        # Send a test message
        test_message = "Hello, can you help me with home inspection questions?"
        client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=test_message
        )
        print(f"Sent message: {test_message}")

        # Run the agent
        run = client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=AZURE_CHAT_AGENT_ID
        )
        print(f"Run status: {run.status}")

        if run.status == "completed":
            # Get the response
            messages = client.agents.messages.list(
                thread_id=thread.id,
                order=ListSortOrder.ASCENDING
            )

            # Find the assistant's response
            for message in messages:
                if message.role == "assistant" and message.text_messages:
                    response = message.text_messages[-1].text.value
                    print(f"Agent response: {response}")
                    break
        else:
            print(f"Run failed: {run.last_error}")

    except Exception as e:
        print(f"Error testing agent: {e}")

if __name__ == "__main__":
    test_chat_agent()
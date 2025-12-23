import os
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

load_dotenv()
 
# 1. Setup the project client
project_client = AIProjectClient(
    endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential()
)
 
# 2. Retrieve the agent using its ID
# Replace "YOUR_AGENT_ID" with the actual ID (e.g., "asst_abc123...")
agent = project_client.agents.get_agent(agent_id=os.environ["AZURE_AI_AGENT_ID"])
 
# 3. Print the instructions
print(f"Agent Name: {agent.name}")
print(f"Instructions: {agent.instructions}")
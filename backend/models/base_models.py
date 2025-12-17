# Input Model
from openai import BaseModel


class QueryInput(BaseModel):
    query: str

# Response Model
class AgentResponse(BaseModel):
    data: dict
    status: str
    status_code: int
    message: str
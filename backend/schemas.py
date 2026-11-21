
from pydantic import BaseModel, Field

class ClassifyRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=5000)

class ClassifyResponse(BaseModel):
    category: str
    confidence: float
    risk_score: int
    risk_level: str
    action: str
    explanation: str
    probabilities: dict[str, float]

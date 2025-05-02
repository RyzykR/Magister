from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class MessageIn(BaseModel):
    service: str
    level: str
    content: str
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)

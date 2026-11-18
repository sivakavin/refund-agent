from pydantic import BaseModel, Field, StringConstraints
from typing import Annotated


class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    thread_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)] = Field(
        description="Client-scoped conversation identifier"
    )


class ChatResponse(BaseModel):
    answer: str
    thread_id: str

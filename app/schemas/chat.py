from typing import Annotated, Literal
from pydantic import BaseModel, Field, StringConstraints


DemoUser = Literal["siva", "inba", "soundhu"]


class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    thread_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)] = Field(
        description="Client-scoped conversation identifier"
    )
    user_name: DemoUser = Field(
        default="siva",
        description="Demo account to use. Defaults to siva for older clients.",
    )


class ChatResponse(BaseModel):
    answer: str
    thread_id: str
    user_name: DemoUser

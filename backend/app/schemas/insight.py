from pydantic import BaseModel, Field


class InsightQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(
        default=None, description="Reuse an existing session/thread id, or omit to start a new one"
    )

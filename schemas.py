from typing import Optional

from pydantic import BaseModel, Field, field_validator


VALID_STATUSES = {"want_to_read", "reading", "read"}


class BookBase(BaseModel):
    title: str
    author: str
    status: str = "want_to_read"
    rating: Optional[int] = Field(default=None, ge=1, le=5)

    @field_validator("title", "author")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field cannot be empty")
        return stripped

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in VALID_STATUSES:
            raise ValueError("status must be reading, read, or want_to_read")
        return value


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    status: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)

    @field_validator("title", "author")
    @classmethod
    def validate_optional_text_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("field cannot be empty")
        return stripped

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in VALID_STATUSES:
            raise ValueError("status must be reading, read, or want_to_read")
        return value


class BookRead(BookBase):
    id: int

    model_config = {"from_attributes": True}


class BookStats(BaseModel):
    total_books: int
    by_status: dict[str, int]
    average_rating_for_read_books: float


class AIChatRequest(BaseModel):
    message: str
    conversation_history: list[dict[str, str]] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message cannot be empty")
        return stripped


class AIChatResponse(BaseModel):
    reply: str
    updated_history: list[dict[str, str]]


class AIAgentRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message cannot be empty")
        return stripped


class AgentStep(BaseModel):
    tool: str
    input: dict[str, object]
    result: dict[str, object]


class AIAgentResponse(BaseModel):
    response: str
    agent_steps: list[AgentStep]

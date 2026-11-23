from typing import Optional
from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    message: str = Field(..., description="Status message")
    filename: str = Field(..., description="Name of the uploaded PDF")
    total_pages: int = Field(..., description="Total pages detected in the PDF")
    total_passages: int = Field(..., description="Total passages indexed from the PDF")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question about the uploaded PDF")


class AskResponse(BaseModel):
    answer: str = Field(..., description="Direct answer to the question")
    page: Optional[int] = Field(None, description="Exact 1-based page number where the answer is found")

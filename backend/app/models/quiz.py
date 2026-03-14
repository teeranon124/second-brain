"""
Quiz Models - สำหรับระบบควิซและ Spaced Repetition
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


class QuizAttempt(BaseModel):
    """Quiz attempt record"""
    node_id: str
    node_label: str
    node_type: str
    book_id: Optional[str] = None
    book_title: Optional[str] = None
    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    hint: Optional[str] = None
    relationships_tested: List[str] = []  # List of related node labels
    created_at: datetime = Field(default_factory=datetime.utcnow)


class QuizAttemptInDB(QuizAttempt):
    """Quiz attempt stored in database"""
    id: str = Field(alias="_id")
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class QuizHistoryResponse(BaseModel):
    """Quiz history statistics"""
    total_attempts: int
    correct_count: int
    incorrect_count: int
    accuracy: float
    recent_attempts: List[QuizAttemptInDB]
    by_category: dict  # {node_type: {correct: int, total: int}}


class QuizGenerateRequest(BaseModel):
    """Request to generate quiz"""
    category: Optional[str] = None  # Filter by node type
    include_relationships: bool = True  # Include relationship questions
    difficulty: str = "medium"  # easy, medium, hard

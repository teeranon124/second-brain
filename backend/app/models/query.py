"""Pydantic Models for Query and Chat"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for graph query"""
    query: str = Field(..., min_length=1, max_length=1000)
    max_hops: Optional[int] = Field(default=3, ge=1, le=5)
    top_k: Optional[int] = Field(default=2, ge=1, le=10)


class QueryStep(BaseModel):
    """Individual step in query execution"""
    step_number: int
    step_type: str  # "dense_retrieval", "bfs_traversal", "summary_generation"
    description: str
    nodes_involved: List[str] = Field(default_factory=list)
    timestamp: float


class BFSResult(BaseModel):
    """Result from BFS traversal"""
    visited_nodes: List[str]
    paths: List[List[str]]
    context: str
    context_node_ids: List[str]  # Nodes that are actually in the context
    max_depth_reached: int


class QueryResponse(BaseModel):
    """Response model for graph query"""
    answer: str
    sources: List[str] = Field(default_factory=list)
    execution_steps: List[QueryStep] = Field(default_factory=list)
    nodes_explored: List[dict] = Field(default_factory=list)
    bfs_result: Optional[BFSResult] = None
    query_time_ms: float


class ChatMessage(BaseModel):
    """Chat message model"""
    role: str = Field(..., pattern="^(user|ai)$")
    text: str
    sources: Optional[List[str]] = None
    is_thinking: Optional[bool] = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatHistoryInDB(BaseModel):
    """Chat history stored in database"""
    id: str = Field(alias="_id")
    session_id: str
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True


class EntityExtractionRequest(BaseModel):
    """Request model for AI entity extraction"""
    text: str = Field(..., min_length=10, max_length=10000)
    extract_links: bool = Field(default=True)


class EntityExtractionResponse(BaseModel):
    """Response model for entity extraction"""
    nodes: List[dict] = Field(default_factory=list)
    links: List[dict] = Field(default_factory=list)
    extraction_time_ms: float

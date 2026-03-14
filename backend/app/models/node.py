"""Pydantic Models for Graph Nodes"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __get_pydantic_json_schema__(cls, schema):
        schema.update(type="string")
        return schema


class NodeBase(BaseModel):
    """Base node model"""
    label: str = Field(..., min_length=1, max_length=200)
    type: str = Field(default="Concept")
    content: str = Field(default="")
    color: Optional[str] = Field(default="#a855f7")
    base_val: Optional[int] = Field(default=15, alias="baseVal")
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)


class NodeCreate(NodeBase):
    """Model for creating a new node"""
    pass


class NodeUpdate(BaseModel):
    """Model for updating an existing node"""
    label: Optional[str] = Field(None, min_length=1, max_length=200)
    type: Optional[str] = None
    content: Optional[str] = None
    color: Optional[str] = None
    base_val: Optional[int] = Field(None, alias="baseVal")
    metadata: Optional[dict[str, Any]] = None


class NodeInDB(NodeBase):
    """Node model as stored in database"""
    id: str = Field(alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    embedding: Optional[List[float]] = None
    embedding_version: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class NodeResponse(NodeBase):
    """Node model for API responses"""
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        from_attributes = True


class NodeWithRelations(NodeResponse):
    """Node with its relationships"""
    outgoing_links: List[dict] = Field(default_factory=list)
    incoming_links: List[dict] = Field(default_factory=list)

"""Pydantic Models for Graph Links/Edges"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.node import NodeResponse


class LinkBase(BaseModel):
    """Base link model"""
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    label: str = Field(..., description="Forward relationship label")
    label_reverse: str = Field(..., description="Backward relationship label", alias="labelReverse")
    curvature: Optional[float] = Field(default=0.0)
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)


class LinkCreate(LinkBase):
    """Model for creating a new link"""
    pass


class LinkUpdate(BaseModel):
    """Model for updating an existing link"""
    label: Optional[str] = None
    label_reverse: Optional[str] = Field(None, alias="labelReverse")
    curvature: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None


class LinkInDB(LinkBase):
    """Link model as stored in database"""
    id: str = Field(alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True


class LinkResponse(LinkBase):
    """Link model for API responses"""
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        from_attributes = True


class GraphData(BaseModel):
    """Complete graph data structure"""
    nodes: list["NodeResponse"] = Field(default_factory=list)
    links: list[LinkResponse] = Field(default_factory=list)

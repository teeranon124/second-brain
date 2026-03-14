"""API Routes for Nodes"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from app.models import NodeCreate, NodeUpdate, NodeResponse, NodeWithRelations
from app.services import GraphService, get_graph_service
from app.db import get_db
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


# ===== Batch Create Request Model =====
class BatchCreateRequest(BaseModel):
    """Request for batch node + link creation"""
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    links: List[Dict[str, Any]] = Field(default_factory=list)
    book: Dict[str, Any] | None = None


class BatchCreateResponse(BaseModel):
    """Response for batch creation"""
    nodes: List[NodeResponse]
    links: List[Dict[str, Any]]
    stats: Dict[str, int]


@router.post("/", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node(
    node_data: NodeCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Create a new node"""
    service = get_graph_service(db)
    return await service.create_node(node_data)


@router.get("/", response_model=List[NodeResponse])
async def get_all_nodes(
    skip: int = 0,
    limit: int = 100,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get all nodes with pagination"""
    service = get_graph_service(db)
    return await service.get_all_nodes(skip=skip, limit=limit)


@router.get("/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get a specific node by ID"""
    service = get_graph_service(db)
    node = await service.get_node(node_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    return node


@router.get("/{node_id}/relations", response_model=NodeWithRelations)
async def get_node_with_relations(
    node_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get a node with all its relationships"""
    service = get_graph_service(db)
    node = await service.get_node_with_relations(node_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    return node


@router.put("/{node_id}", response_model=NodeResponse)
async def update_node(
    node_id: str,
    node_update: NodeUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Update a node"""
    service = get_graph_service(db)
    node = await service.update_node(node_id, node_update)
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    return node


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    node_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Delete a node"""
    service = get_graph_service(db)
    deleted = await service.delete_node(node_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Node not found")


@router.get("/{node_id}/suggest-connections")
async def suggest_connections(
    node_id: str,
    top_k: int = 5,
    threshold: float = 0.5,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Find existing nodes semantically similar to a given node.
    Use this right after manual node creation to suggest smart connections.
    Returns a list of {id, label, type, content, similarity} dicts.
    """
    service = get_graph_service(db)
    return await service.suggest_connections(node_id, top_k=top_k, threshold=threshold)


@router.get("/search/", response_model=List[NodeResponse])
async def search_nodes(
    q: str,
    limit: int = 10,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Search nodes by text"""
    service = get_graph_service(db)
    return await service.search_nodes(query=q, limit=limit)


@router.get("/similar/{label}", response_model=NodeResponse)
async def find_similar_node(
    label: str,
    threshold: float = 0.8,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Find node with similar label (Entity Matching)
    
    Useful for deduplication and entity resolution
    """
    service = get_graph_service(db)
    similar_node = await service.find_similar_node(label, threshold)
    
    if not similar_node:
        raise HTTPException(
            status_code=404, 
            detail=f"No similar node found for '{label}' (threshold: {threshold})"
        )
    
    return similar_node


@router.post("/batch-create", response_model=BatchCreateResponse)
async def batch_create_nodes_and_links(
    request: BatchCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Batch create nodes + links with entity matching and deduplication
    
    - Automatically merges duplicate nodes (vector similarity ≥ 0.75)
    - Skips duplicate links
    - Fast: Single round-trip to backend
    
    Returns:
        - nodes: Created/matched nodes
        - links: Created links
        - stats: {new_nodes, merged_nodes, new_links, skipped_links}
    """
    service = get_graph_service(db)
    result = await service.batch_create_with_dedup(
        nodes=request.nodes,
        links=request.links,
        book_data=request.book,
    )
    
    return BatchCreateResponse(
        nodes=result["nodes"],
        links=[link.model_dump() for link in result["links"]],
        stats=result["stats"]
    )

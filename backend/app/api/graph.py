"""API Routes for Graph Operations"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

from app.models import GraphData, NodeCreate, LinkCreate, NodeResponse, LinkResponse
from app.services import GraphService, get_graph_service
from app.db import get_db
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/", response_model=GraphData)
async def get_full_graph(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get the complete graph (all nodes and links)"""
    service = get_graph_service(db)
    return await service.get_full_graph()


@router.post("/bulk/nodes", response_model=List[NodeResponse])
async def bulk_create_nodes(
    nodes: List[NodeCreate],
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Create multiple nodes at once"""
    service = get_graph_service(db)
    return await service.bulk_create_nodes(nodes)


@router.post("/bulk/links", response_model=List[LinkResponse])
async def bulk_create_links(
    links: List[LinkCreate],
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Create multiple links at once"""
    service = get_graph_service(db)
    return await service.bulk_create_links(links)


@router.post("/import", response_model=GraphData)
async def import_graph(
    graph_data: GraphData,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Import a complete graph (nodes + links)"""
    service = get_graph_service(db)
    
    # Create nodes first
    node_creates = [
        NodeCreate(**node.model_dump(exclude={"id", "created_at", "updated_at"}))
        for node in graph_data.nodes
    ]
    created_nodes = await service.bulk_create_nodes(node_creates)
    
    # Create links
    link_creates = [
        LinkCreate(**link.model_dump(exclude={"id", "created_at", "updated_at"}))
        for link in graph_data.links
    ]
    created_links = await service.bulk_create_links(link_creates)
    
    return GraphData(nodes=created_nodes, links=created_links)

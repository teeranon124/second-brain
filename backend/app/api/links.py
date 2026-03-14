"""API Routes for Links"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict

from app.models import LinkCreate, LinkUpdate, LinkResponse
from app.services import GraphService, get_graph_service
from app.db import get_db
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/api/links", tags=["links"])


@router.post("/", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
async def create_link(
    link_data: LinkCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Create a new link between nodes"""
    service = get_graph_service(db)
    
    try:
        return await service.create_link(link_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[LinkResponse])
async def get_all_links(
    skip: int = 0,
    limit: int = 1000,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get all links with pagination"""
    service = get_graph_service(db)
    return await service.get_all_links(skip=skip, limit=limit)


@router.get("/{link_id}", response_model=LinkResponse)
async def get_link(
    link_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get a specific link by ID"""
    service = get_graph_service(db)
    link = await service.get_link(link_id)
    
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    
    return link


@router.put("/{link_id}", response_model=LinkResponse)
async def update_link(
    link_id: str,
    link_update: LinkUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Update a link"""
    service = get_graph_service(db)
    link = await service.update_link(link_id, link_update)
    
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    
    return link


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    link_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Delete a link"""
    service = get_graph_service(db)
    deleted = await service.delete_link(link_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")


@router.get("/node/{node_id}", response_model=Dict[str, List[LinkResponse]])
async def get_node_links(
    node_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get all links for a specific node"""
    service = get_graph_service(db)
    return await service.get_node_links(node_id)

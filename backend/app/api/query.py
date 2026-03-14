"""API Routes for Query and RAG Operations"""

from fastapi import APIRouter, HTTPException, Depends, status

from app.models import (
    QueryRequest,
    QueryResponse,
    EntityExtractionRequest,
    EntityExtractionResponse,
)
from app.services import RAGService, get_rag_service, GeminiService, get_gemini_service
from app.db import get_db
from motor.motor_asyncio import AsyncIOMotorDatabase
import time

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("/", response_model=QueryResponse)
async def query_graph(
    query_request: QueryRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Query the graph using GraphRAG pipeline:
    1. Dense Retrieval (Vector Search)
    2. BFS Traversal
    3. Answer Generation
    """
    service = get_rag_service(db)
    
    try:
        return await service.query_graph(query_request)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {str(e)}"
        )


@router.post("/extract", response_model=EntityExtractionResponse)
async def extract_entities(
    request: EntityExtractionRequest,
):
    """
    Extract entities and relationships from text using Gemini AI
    
    This implements the Knowledge Extraction component of GraphRAG
    """
    start_time = time.time()
    gemini_service = get_gemini_service()
    
    try:
        extracted_data = await gemini_service.extract_entities(request.text)
        
        extraction_time_ms = (time.time() - start_time) * 1000
        
        return EntityExtractionResponse(
            nodes=extracted_data.get("nodes", []),
            links=extracted_data.get("links", []) if request.extract_links else [],
            extraction_time_ms=extraction_time_ms,
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Entity extraction failed: {str(e)}"
        )


@router.get("/health")
async def query_health():
    """Check query service health"""
    return {
        "status": "healthy",
        "service": "GraphRAG Query Engine",
    }


@router.post("/pathfind")
async def find_path(
    source_id: str,
    target_id: str,
    max_depth: int = 5,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Find shortest path between two nodes using BFS
    Returns path with AI-generated explanation of the connection
    """
    service = get_rag_service(db)
    gemini_service = get_gemini_service()
    
    try:
        # Use BFS to find path
        from bson import ObjectId
        
        # Get source and target nodes
        source_node = await db.nodes.find_one({"_id": ObjectId(source_id)})
        target_node = await db.nodes.find_one({"_id": ObjectId(target_id)})
        
        if not source_node or not target_node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Find path using BFS
        bfs_result = await service._bfs_traversal(
            starting_nodes=[source_id],
            max_hops=max_depth
        )
        
        # Extract path from BFS result
        # Reconstruct path from visited nodes
        path = []
        visited = {}
        queue = [(source_id, [source_id])]
        
        while queue:
            current_id, current_path = queue.pop(0)
            
            if current_id == target_id:
                path = current_path
                break
            
            if current_id in visited:
                continue
            visited[current_id] = True
            
            # Find neighbors
            links = await db.links.find({
                "$or": [
                    {"source": ObjectId(current_id)},
                    {"target": ObjectId(current_id)},
                    {"source": current_id},
                    {"target": current_id},
                ]
            }).to_list(None)
            
            for link in links:
                source_val = str(link.get("source"))
                target_val = str(link.get("target"))
                next_id = target_val if source_val == current_id else source_val
                if next_id not in visited:
                    queue.append((next_id, current_path + [next_id]))
        
        if not path or len(path) < 2:
            return {
                "found": False,
                "path": [],
                "explanation": f"No path found between {source_node['label']} and {target_node['label']} within {max_depth} hops."
            }
        
        # Get full node and link data for path
        path_nodes = []
        path_links = []
        
        for i, node_id in enumerate(path):
            node = await db.nodes.find_one({"_id": ObjectId(node_id)})
            if node:
                path_nodes.append({
                    "id": str(node["_id"]),
                    "label": node["label"],
                    "type": node.get("type"),
                    "content": node.get("content", "")
                })
            
            if i < len(path) - 1:
                # Find link between current and next node
                link = await db.links.find_one({
                    "$or": [
                        {"source": ObjectId(path[i]), "target": ObjectId(path[i+1])},
                        {"source": ObjectId(path[i+1]), "target": ObjectId(path[i])},
                        {"source": path[i], "target": path[i+1]},
                        {"source": path[i+1], "target": path[i]},
                    ]
                })
                if link:
                    path_links.append({
                        "source": str(link["source"]),
                        "target": str(link["target"]),
                        "label": link.get("label", "connected to")
                    })
        
        # Generate AI explanation
        path_description = " → ".join([n["label"] for n in path_nodes])
        context = "\n".join([f"- {n['label']}: {n['content'][:200]}" for n in path_nodes])
        
        explanation_prompt = f"""Path Found: {path_description}

Context of nodes:
{context}

Please explain the connection/relationship between {source_node['label']} and {target_node['label']} based on this path. 
Keep it concise (2-3 sentences) and focus on why these nodes are connected."""
        
        explanation = await gemini_service.generate_content(
            prompt=explanation_prompt,
            temperature=0.7
        )

        # Reinforce memory on successful recall path
        await service._apply_spreading_activation(
            visited_node_ids=[p["id"] for p in path_nodes],
            paths=[[str(path[i]), str(path[i + 1])] for i in range(len(path) - 1)],
        )
        
        return {
            "found": True,
            "path": path_nodes,
            "links": path_links,
            "explanation": explanation,
            "distance": len(path) - 1
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pathfinding failed: {str(e)}"
        )

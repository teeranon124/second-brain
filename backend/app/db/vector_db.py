"""MongoDB Atlas Vector Search Service"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Any
import logging
from bson import ObjectId

from app.config import get_settings

logger = logging.getLogger(__name__)


class VectorDatabase:
    """MongoDB Atlas Vector Search Manager"""

    db: Optional[AsyncIOMotorDatabase] = None
    nodes_collection = None

    async def connect(self, db: AsyncIOMotorDatabase):
        """Connect to MongoDB Atlas and set up vector search"""
        
        self.db = db
        self.nodes_collection = db.nodes
        
        logger.info("✅ Atlas Vector Search initialized")

    async def disconnect(self):
        """Disconnect (no-op for MongoDB, handled by main connection)"""
        logger.info("Atlas Vector Search closed")

    async def upsert_node(
        self,
        node_id: str,
        embedding: List[float],
        payload: Dict[str, Any],
    ):
        """
        Insert or update a node embedding in MongoDB
        
        NOTE: Embedding is stored directly in the nodes collection
        This method only ensures the embedding field is updated
        """
        
        try:
            # Convert string ID to ObjectId if needed
            if isinstance(node_id, str):
                object_id = ObjectId(node_id)
            else:
                object_id = node_id
            
            # Update embedding field in nodes collection
            result = await self.nodes_collection.update_one(
                {"_id": object_id},
                {"$set": {"embedding": embedding}}
            )
            
            if result.matched_count == 0:
                logger.warning(f"Node {node_id} not found for embedding update")
            
        except Exception as e:
            logger.error(f"Failed to upsert embedding for node {node_id}: {e}")
            raise

    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar nodes using MongoDB Atlas Vector Search
        
        Uses $vectorSearch aggregation pipeline stage
        """
        
        try:
            # Build vector search pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",  # Atlas vector index name
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": top_k * 10,  # Internal candidates for better accuracy
                        "limit": top_k,
                    }
                },
                {
                    "$addFields": {
                        "score": {"$meta": "vectorSearchScore"}
                    }
                },
                # Filter by score threshold
                {
                    "$match": {
                        "score": {"$gte": score_threshold}
                    }
                },
                # Project fields we need
                {
                    "$project": {
                        "_id": 1,
                        "label": 1,
                        "content": 1,
                        "type": 1,
                        "score": 1,
                        "embedding": 0  # Don't return embedding (large field)
                    }
                }
            ]
            
            # Add additional filters if provided
            if filters:
                pipeline.insert(2, {"$match": filters})
            
            # Execute aggregation
            cursor = self.nodes_collection.aggregate(pipeline)
            results = await cursor.to_list(length=top_k)
            
            # Format results to match old Qdrant interface
            formatted_results = [
                {
                    "id": str(result["_id"]),
                    "score": result["score"],
                    "payload": {
                        "label": result.get("label", ""),
                        "content": result.get("content", ""),
                        "type": result.get("type", ""),
                    }
                }
                for result in results
            ]
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            logger.error(f"Note: Make sure Atlas Vector Search index 'vector_index' exists!")
            return []

    async def delete_node(self, node_id: str):
        """
        Delete node embedding (no-op - handled by node deletion in MongoDB)
        
        Embedding is stored in nodes collection, so it's automatically deleted
        when the node is deleted
        """
        # No action needed - embedding is part of node document
        pass

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve node from MongoDB"""
        
        try:
            # Convert string ID to ObjectId
            if isinstance(node_id, str):
                object_id = ObjectId(node_id)
            else:
                object_id = node_id
            
            node = await self.nodes_collection.find_one({"_id": object_id})
            
            if node:
                return {
                    "id": str(node["_id"]),
                    "payload": {
                        "label": node.get("label", ""),
                        "content": node.get("content", ""),
                        "type": node.get("type", ""),
                    }
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving node {node_id}: {e}")
            return None


# Global instance
vector_db = VectorDatabase()


async def get_vector_db() -> VectorDatabase:
    """FastAPI dependency"""
    return vector_db
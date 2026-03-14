"""Re-index all nodes to Qdrant with embeddings"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import Settings
from app.db.vector_db import vector_db
from app.services.embedding_service import get_embedding_service

settings = Settings()


async def reindex_all_nodes():
    """Re-index all MongoDB nodes to Qdrant"""
    print("🔄 Starting re-indexing process...")
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]
    nodes_collection = db.nodes
    
    # Connect to Qdrant
    await vector_db.connect()
    print("✅ Connected to Qdrant")
    
    # Get embedding service
    embedding_service = get_embedding_service()
    
    # Get all nodes
    nodes = await nodes_collection.find().to_list(None)
    print(f"📊 Found {len(nodes)} nodes to index")
    
    success_count = 0
    error_count = 0
    
    for i, node in enumerate(nodes, 1):
        try:
            node_id = str(node["_id"])
            label = node["label"]
            content = node.get("content", "")
            
            # Generate embedding
            text = f"{label}. {content}".strip()
            embedding = await embedding_service.encode(text)
            
            # Upsert to Qdrant
            await vector_db.upsert_node(
                node_id=node_id,
                embedding=embedding,
                payload={
                    "label": label,
                    "type": node.get("type", "Concept"),
                    "content": content,
                }
            )
            
            success_count += 1
            print(f"✅ [{i}/{len(nodes)}] Indexed: {label}")
            
        except Exception as e:
            error_count += 1
            print(f"❌ [{i}/{len(nodes)}] Failed: {label} - {e}")
    
    print(f"\n🎉 Re-indexing complete!")
    print(f"   Success: {success_count}")
    print(f"   Errors: {error_count}")
    
    # Close connections
    await vector_db.close()
    client.close()


if __name__ == "__main__":
    asyncio.run(reindex_all_nodes())

"""Clear Database Script"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import mongodb, vector_db


async def clear_database():
    """Clear all data from databases"""
    
    print("⚠️  Clearing all data from databases...")
    
    # Connect to databases
    await mongodb.connect()
    await vector_db.connect()
    
    db = mongodb.get_database()
    
    # Clear MongoDB collections
    nodes_result = await db.nodes.delete_many({})
    links_result = await db.links.delete_many({})
    chat_result = await db.chat_history.delete_many({})
    logs_result = await db.query_logs.delete_many({})
    
    print(f"  🗑️  Deleted {nodes_result.deleted_count} nodes")
    print(f"  🗑️  Deleted {links_result.deleted_count} links")
    print(f"  🗑️  Deleted {chat_result.deleted_count} chat histories")
    print(f"  🗑️  Deleted {logs_result.deleted_count} query logs")
    
    # Clear Qdrant collection (recreate it)
    try:
        vector_db.client.delete_collection(collection_name=vector_db.collection_name)
        await vector_db._ensure_collection()
        print(f"  🗑️  Cleared Qdrant collection: {vector_db.collection_name}")
    except Exception as e:
        print(f"  ⚠️  Could not clear Qdrant: {e}")
    
    # Disconnect
    await mongodb.disconnect()
    await vector_db.disconnect()
    
    print("\n✅ Database cleared successfully!")


if __name__ == "__main__":
    asyncio.run(clear_database())

"""
Migration Script: Qdrant → MongoDB Atlas Vector Search

This script:
1. Reads all nodes from MongoDB
2. Generates embeddings for nodes (or copies from Qdrant if available)
3. Adds 'embedding' field to nodes collection
4. Creates Atlas Vector Search Index (manual step - see instructions)
"""

import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from sentence_transformers import SentenceTransformer
from typing import List
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AtlasMigration:
    """Migration handler for Atlas Vector Search"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self.db = None
        self.model = None
        
    async def connect(self):
        """Connect to MongoDB Atlas"""
        logger.info(f"🔌 Connecting to MongoDB Atlas...")
        
        self.client = AsyncIOMotorClient(
            self.settings.mongodb_uri,
            serverSelectionTimeoutMS=10000
        )
        
        self.db = self.client[self.settings.mongodb_db_name]
        
        # Test connection
        await self.client.admin.command('ping')
        logger.info(f"✅ Connected to MongoDB Atlas: {self.settings.mongodb_db_name}")
        
    async def load_embedding_model(self):
        """Load sentence transformer model"""
        logger.info(f"📦 Loading embedding model: {self.settings.embedding_model}")
        
        self.model = SentenceTransformer(self.settings.embedding_model)
        
        logger.info(f"✅ Model loaded (dimension: {self.settings.embedding_dimension})")
        
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        embedding = self.model.encode(text).tolist()
        return embedding
        
    async def migrate_embeddings(self):
        """Migrate embeddings to MongoDB nodes collection"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 Starting Embedding Migration")
        logger.info(f"{'='*60}\n")
        
        # Count total nodes
        total_nodes = await self.db.nodes.count_documents({})
        logger.info(f"📊 Total nodes to migrate: {total_nodes}")
        
        if total_nodes == 0:
            logger.warning("⚠️  No nodes found in database")
            return
        
        # Check if embeddings already exist
        nodes_with_embeddings = await self.db.nodes.count_documents({
            "embedding": {"$exists": True}
        })
        
        if nodes_with_embeddings > 0:
            logger.warning(f"⚠️  Found {nodes_with_embeddings} nodes with existing embeddings")
            response = input("Do you want to regenerate all embeddings? (y/N): ")
            if response.lower() != 'y':
                logger.info("❌ Migration cancelled")
                return
        
        # Fetch all nodes
        logger.info(f"📥 Fetching all nodes from MongoDB...")
        cursor = self.db.nodes.find({})
        nodes = await cursor.to_list(length=None)
        
        logger.info(f"✅ Fetched {len(nodes)} nodes")
        
        # Generate embeddings
        logger.info(f"\n🔄 Generating embeddings...")
        
        updated_count = 0
        
        for i, node in enumerate(nodes, 1):
            node_id = node["_id"]
            label = node.get("label", "")
            content = node.get("content", "")
            
            # Combine label and content for embedding
            text = f"{label}. {content}".strip()
            
            if not text:
                logger.warning(f"⚠️  Node {node_id} has no text, skipping...")
                continue
            
            # Generate embedding
            embedding = self.generate_embedding(text)
            
            # Update node with embedding
            await self.db.nodes.update_one(
                {"_id": node_id},
                {"$set": {"embedding": embedding}}
            )
            
            updated_count += 1
            
            # Progress indicator
            if i % 10 == 0 or i == len(nodes):
                logger.info(f"📍 Progress: {i}/{len(nodes)} ({(i/len(nodes)*100):.1f}%)")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Migration Complete!")
        logger.info(f"{'='*60}")
        logger.info(f"📊 Updated {updated_count}/{total_nodes} nodes with embeddings")
        
    async def create_vector_index_instructions(self):
        """Print instructions for creating Atlas Vector Search Index"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 NEXT STEP: Create Atlas Vector Search Index")
        logger.info(f"{'='*60}\n")
        
        logger.info(f"🌐 Go to MongoDB Atlas Console:")
        logger.info(f"   https://cloud.mongodb.com/\n")
        
        logger.info(f"📍 Navigate to:")
        logger.info(f"   Your Cluster → Search → Create Search Index\n")
        
        logger.info(f"⚙️  Index Configuration:")
        logger.info(f"   - Database: {self.settings.mongodb_db_name}")
        logger.info(f"   - Collection: nodes")
        logger.info(f"   - Index Name: vector_index")
        logger.info(f"   - Index Type: Vector Search\n")
        
        logger.info(f"📝 JSON Configuration:")
        
        index_config = """{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 384,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "type"
    },
    {
      "type": "filter",
      "path": "label"
    }
  ]
}"""
        
        print(f"\n{index_config}\n")
        
        logger.info(f"✅ After creating the index, wait 2-3 minutes for it to build")
        logger.info(f"✅ Then you can run the backend with Atlas Vector Search!\n")
        
    async def verify_migration(self):
        """Verify migration was successful"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 Verification")
        logger.info(f"{'='*60}\n")
        
        # Check total nodes
        total_nodes = await self.db.nodes.count_documents({})
        
        # Check nodes with embeddings
        nodes_with_embeddings = await self.db.nodes.count_documents({
            "embedding": {"$exists": True}
        })
        
        # Check nodes without embeddings
        nodes_without_embeddings = await self.db.nodes.count_documents({
            "embedding": {"$exists": False}
        })
        
        logger.info(f"📊 Total nodes: {total_nodes}")
        logger.info(f"✅ Nodes with embeddings: {nodes_with_embeddings}")
        logger.info(f"❌ Nodes without embeddings: {nodes_without_embeddings}")
        
        if nodes_without_embeddings > 0:
            logger.warning(f"\n⚠️  {nodes_without_embeddings} nodes are missing embeddings!")
        else:
            logger.info(f"\n✅ All nodes have embeddings!")
        
        # Sample check
        sample = await self.db.nodes.find_one({"embedding": {"$exists": True}})
        
        if sample:
            embedding_length = len(sample.get("embedding", []))
            logger.info(f"\n🔬 Sample Node:")
            logger.info(f"   Label: {sample.get('label')}")
            logger.info(f"   Embedding Length: {embedding_length}")
            logger.info(f"   Expected: {self.settings.embedding_dimension}")
            
            if embedding_length != self.settings.embedding_dimension:
                logger.error(f"❌ Embedding dimension mismatch!")
            else:
                logger.info(f"✅ Embedding dimension correct!")
        
    async def run(self):
        """Run full migration"""
        
        try:
            await self.connect()
            await self.load_embedding_model()
            await self.migrate_embeddings()
            await self.verify_migration()
            await self.create_vector_index_instructions()
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise
        
        finally:
            if self.client:
                self.client.close()
                logger.info(f"\n🔌 MongoDB connection closed")


async def main():
    """Main entry point"""
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║          MongoDB Atlas Vector Search Migration              ║
║                                                              ║
║  This script will:                                          ║
║  1. ✅ Add embedding field to all nodes                     ║
║  2. ✅ Generate embeddings using SentenceTransformer        ║
║  3. ✅ Verify migration completed successfully              ║
║  4. 📋 Provide instructions for Atlas index creation        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    migration = AtlasMigration()
    await migration.run()
    
    print(f"\n{'='*60}")
    print(f"✅ Migration script completed!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())

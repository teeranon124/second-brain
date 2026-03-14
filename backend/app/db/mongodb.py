"""MongoDB Database Connection and Operations"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


class MongoDB:
    """MongoDB connection manager"""
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    async def connect(self):
        """Connect to MongoDB"""
        settings = get_settings()
        
        logger.info(f"Connecting to MongoDB: {settings.mongodb_db_name}")
        
        self.client = AsyncIOMotorClient(
            settings.mongodb_uri,
            maxPoolSize=10,
            minPoolSize=1,
            serverSelectionTimeoutMS=5000,
        )
        
        self.db = self.client[settings.mongodb_db_name]
        
        # Create indexes
        await self._create_indexes()
        
        logger.info("✅ MongoDB connected successfully")
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    async def _create_indexes(self):
        """Create necessary indexes for optimal query performance"""
        
        # Nodes collection indexes
        await self.db.nodes.create_index("label")
        await self.db.nodes.create_index("type")
        await self.db.nodes.create_index("created_at")
        await self.db.nodes.create_index([("label", "text"), ("content", "text")])
        
        # Links collection indexes
        await self.db.links.create_index("source")
        await self.db.links.create_index("target")
        await self.db.links.create_index([("source", 1), ("target", 1)], unique=True)
        
        # Quiz attempts indexes
        await self.db.quiz_attempts.create_index("node_id")
        await self.db.quiz_attempts.create_index("node_type")
        await self.db.quiz_attempts.create_index("created_at")
        await self.db.quiz_attempts.create_index([("created_at", -1)])  # For recent attempts
        
        # Query logs indexes (for analytics)
        await self.db.query_logs.create_index("created_at")
        await self.db.query_logs.create_index("query_hash")

        # Books collection indexes (book-based notebook)
        await self.db.books.create_index("title")
        await self.db.books.create_index("source_type")
        await self.db.books.create_index("created_at")
        await self.db.books.create_index("updated_at")
        await self.db.books.create_index("node_ids")
        
        logger.info("✅ Database indexes created")
    
    def get_database(self) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if self.db is None:
            raise RuntimeError("Database not initialized. Call connect() first.")
        return self.db


# Global database instance
mongodb = MongoDB()


async def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency to get database instance"""
    return mongodb.get_database()

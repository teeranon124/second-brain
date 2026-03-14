"""Embedding Service using Sentence Transformers"""

from sentence_transformers import SentenceTransformer
from typing import List, Union
import logging
import asyncio
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings"""
    
    def __init__(self):
        self.model = None
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Load the embedding model (lazy loading)"""
        if self.model is not None:
            return
        
        async with self._lock:
            if self.model is not None:
                return
            
            settings = get_settings()
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            
            # Run model loading in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: SentenceTransformer(settings.embedding_model)
            )
            
            logger.info("✅ Embedding model loaded successfully")
    
    async def encode(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Generate embeddings for text(s)
        
        Args:
            texts: Single text string or list of texts
            
        Returns:
            Embedding(s) as list(s) of floats
        """
        await self.initialize()
        
        # Convert single text to list for batch processing
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]
        
        # Generate embeddings in thread pool
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.model.encode(texts, convert_to_numpy=True)
        )
        
        # Convert numpy arrays to lists
        embeddings_list = [emb.tolist() for emb in embeddings]
        
        # Return single embedding if input was single text
        return embeddings_list[0] if is_single else embeddings_list
    
    async def encode_nodes(self, nodes: List[dict]) -> List[List[float]]:
        """
        Generate embeddings for a list of nodes
        
        Each node's embedding is created from: label + content
        """
        texts = [f"{node['label']}. {node.get('content', '')}" for node in nodes]
        return await self.encode(texts)
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        settings = get_settings()
        return settings.embedding_dimension


# Global embedding service instance
@lru_cache()
def get_embedding_service() -> EmbeddingService:
    """Get singleton embedding service instance"""
    return EmbeddingService()

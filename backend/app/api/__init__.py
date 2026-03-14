"""API Routes Package"""

from fastapi import APIRouter
from app.api import nodes, links, graph, query, documents, quiz, books

api_router = APIRouter()

# Include all routers  
api_router.include_router(nodes.router)
api_router.include_router(links.router)
api_router.include_router(graph.router)
api_router.include_router(query.router)
api_router.include_router(documents.router)
api_router.include_router(quiz.router)
api_router.include_router(books.router)

__all__ = ["api_router"]

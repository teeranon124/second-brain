"""Models Package"""

from app.models.node import (
    NodeBase,
    NodeCreate,
    NodeUpdate,
    NodeInDB,
    NodeResponse,
    NodeWithRelations,
)
from app.models.link import (
    LinkBase,
    LinkCreate,
    LinkUpdate,
    LinkInDB,
    LinkResponse,
    GraphData,
)
from app.models.query import (
    QueryRequest,
    QueryResponse,
    QueryStep,
    ChatMessage,
    ChatHistoryInDB,
    EntityExtractionRequest,
    EntityExtractionResponse,
    BFSResult,
)
from app.models.quiz import (
    QuizAttempt,
    QuizAttemptInDB,
    QuizHistoryResponse,
    QuizGenerateRequest,
)

__all__ = [
    # Node models
    "NodeBase",
    "NodeCreate",
    "NodeUpdate",
    "NodeInDB",
    "NodeResponse",
    "NodeWithRelations",
    # Link models
    "LinkBase",
    "LinkCreate",
    "LinkUpdate",
    "LinkInDB",
    "LinkResponse",
    "GraphData",
    # Query models
    "QueryRequest",
    "QueryResponse",
    "QueryStep",
    "ChatMessage",
    "ChatHistoryInDB",
    "EntityExtractionRequest",
    "EntityExtractionResponse",
    "BFSResult",
    # Quiz models
    "QuizAttempt",
    "QuizAttemptInDB",
    "QuizHistoryResponse",
    "QuizGenerateRequest",
]

# Rebuild models to resolve forward references
GraphData.model_rebuild()

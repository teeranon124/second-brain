"""API Routes for Book-based Notebook Views"""

from datetime import datetime
import re

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.db import get_db
from app.services import get_graph_service, get_gemini_service

router = APIRouter(prefix="/api/books", tags=["books"])


class BookUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    full_text: str = Field(..., min_length=10)
    source_type: str = Field(default="text")
    filename: str | None = None


@router.get("/")
async def list_books(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Return books sorted by latest update (newest first)."""
    books = await db.books.find().sort("updated_at", -1).to_list(length=200)
    for book in books:
        book["id"] = str(book.pop("_id"))
        # Keep payload light for list endpoint
        if "full_text" in book and isinstance(book["full_text"], str):
            book["preview"] = book["full_text"][:300]
            book["full_text_length"] = len(book["full_text"])
            del book["full_text"]
    return books


@router.get("/clusters/overview")
async def get_book_clusters(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Return a graph-like structure of book clusters where edges mean shared node IDs.
    Useful for rendering intersecting book groups.
    """
    books = await db.books.find().to_list(length=500)

    nodes = []
    edges = []

    for b in books:
        nodes.append(
            {
                "id": str(b.get("_id")),
                "title": b.get("title", "Untitled Book"),
                "node_count": len(b.get("node_ids", [])),
                "source_type": b.get("source_type", "text"),
            }
        )

    for i in range(len(books)):
        a = books[i]
        a_ids = set(a.get("node_ids", []))
        if not a_ids:
            continue

        for j in range(i + 1, len(books)):
            b = books[j]
            b_ids = set(b.get("node_ids", []))
            if not b_ids:
                continue

            shared = list(a_ids.intersection(b_ids))
            if not shared:
                continue

            edges.append(
                {
                    "source": str(a.get("_id")),
                    "target": str(b.get("_id")),
                    "shared_count": len(shared),
                    "shared_node_ids": shared,
                }
            )

    return {
        "nodes": nodes,
        "edges": edges,
    }


@router.get("/by-node/{node_id}")
async def get_books_by_node(node_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """List books that reference a specific node id."""
    books = await db.books.find({"node_ids": node_id}).sort("updated_at", -1).to_list(length=200)
    result = []
    for b in books:
        result.append(
            {
                "id": str(b.get("_id")),
                "title": b.get("title", "Untitled Book"),
                "source_type": b.get("source_type", "text"),
                "updated_at": b.get("updated_at"),
            }
        )
    return result


@router.get("/{book_id}")
async def get_book(book_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Return full book details with full text, highlights, and related nodes."""
    from bson import ObjectId

    try:
        oid = ObjectId(book_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid book id")

    book = await db.books.find_one({"_id": oid})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book["id"] = str(book.pop("_id"))
    return book


@router.put("/{book_id}")
async def update_book(
    book_id: str,
    request: BookUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Update a book and synchronize its nodes/links against current graph memory.
    This keeps DB consistency: book text <-> extracted nodes <-> relationships.
    """
    from bson import ObjectId

    try:
        oid = ObjectId(book_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid book id")

    existing_book = await db.books.find_one({"_id": oid})
    if not existing_book:
        raise HTTPException(status_code=404, detail="Book not found")

    gemini_service = get_gemini_service()
    graph_service = get_graph_service(db)

    # Re-extract entities from updated text
    extracted = await gemini_service.extract_entities(request.full_text)
    nodes = extracted.get("nodes", [])
    links = extracted.get("links", [])

    # Reuse/merge knowledge in existing graph, do not duplicate tiny variations.
    # IMPORTANT: do not persist a new book snapshot while editing an existing book.
    result = await graph_service.batch_create_with_dedup(
        nodes=nodes,
        links=links,
        book_data=None,
        persist_book_memory=False,
    )

    # Replace current book snapshot with updated text and latest node mapping
    used_nodes = [n for n in result.get("nodes", []) if n is not None]
    node_ids = [n.id for n in used_nodes]
    node_refs = [
        {
            "node_id": n.id,
            "label": n.label,
            "type": n.type,
        }
        for n in used_nodes
    ]

    highlights = []
    for n in used_nodes:
        label = (n.label or "").strip()
        if not label:
            continue
        for m in re.finditer(re.escape(label), request.full_text, flags=re.IGNORECASE):
            highlights.append(
                {
                    "node_id": n.id,
                    "label": label,
                    "start": m.start(),
                    "end": m.end(),
                }
            )
            if len([h for h in highlights if h["node_id"] == n.id]) >= 5:
                break

    now = datetime.utcnow()
    await db.books.update_one(
        {"_id": oid},
        {
            "$set": {
                "title": request.title,
                "source_type": request.source_type,
                "filename": request.filename,
                "full_text": request.full_text,
                "node_ids": list(dict.fromkeys(node_ids)),
                "node_refs": node_refs,
                "highlights": highlights,
                "updated_at": now,
            }
        },
    )

    updated = await db.books.find_one({"_id": oid})
    updated["id"] = str(updated.pop("_id"))

    return {
        "book": updated,
        "sync_stats": result.get("stats", {}),
    }


@router.delete("/{book_id}")
async def delete_book(book_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Delete a book and cascade delete all nodes that belong to the book,
    including their links and vector entries.
    """
    from bson import ObjectId

    try:
        oid = ObjectId(book_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid book id")

    book = await db.books.find_one({"_id": oid})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    graph_service = get_graph_service(db)
    node_ids = list(dict.fromkeys(book.get("node_ids", []) or []))

    deleted_nodes = 0
    for node_id in node_ids:
        try:
            deleted = await graph_service.delete_node(str(node_id))
            if deleted:
                deleted_nodes += 1
        except Exception:
            # Continue deleting others for best-effort cleanup
            pass

    await db.books.delete_one({"_id": oid})

    return {
        "ok": True,
        "deleted_book_id": book_id,
        "deleted_nodes": deleted_nodes,
    }

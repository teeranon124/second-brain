"""Quiz API Endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from datetime import datetime
from bson import ObjectId
import logging

from app.db.mongodb import get_db
from app.models.quiz import (
    QuizAttempt,
    QuizAttemptInDB,
    QuizHistoryResponse,
    QuizGenerateRequest,
)
from app.services.gemini_service import get_gemini_service

router = APIRouter(prefix="/api/quiz", tags=["quiz"])
logger = logging.getLogger(__name__)


@router.get("/books")
async def get_quiz_books(db: AsyncIOMotorDatabase = Depends(get_db)):
    """List books available for book-based quizzes."""
    books = await db.books.find().sort("updated_at", -1).to_list(length=200)
    return {
        "books": [
            {
                "id": str(b.get("_id")),
                "title": b.get("title", "Untitled Book"),
                "node_count": len(b.get("node_ids", [])),
                "updated_at": b.get("updated_at"),
            }
            for b in books
        ]
    }


@router.get("/by-book/{book_id}/question")
async def generate_book_quiz_question(
    book_id: str,
    difficulty: str = Query("medium", pattern="^(easy|medium|hard)$"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Generate one quiz question from a selected book's actual content."""
    try:
        oid = ObjectId(book_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid book id")

    book = await db.books.find_one({"_id": oid})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    full_text = (book.get("full_text") or "").strip()
    if len(full_text) < 20:
        raise HTTPException(status_code=400, detail="Book has insufficient text")

    node_refs = book.get("node_refs", [])
    focus_nodes = ", ".join([n.get("label", "") for n in node_refs[:8] if n.get("label")])

    gemini = get_gemini_service()
    prompt = f"""จากหนังสือ: {book.get('title', 'Untitled Book')}

ความยาก: {difficulty}
โหนดสำคัญ: {focus_nodes if focus_nodes else 'ไม่ระบุ'}

ข้อความจริงจากหนังสือ:
{full_text[:3500]}

สร้างคำถาม 1 ข้อแบบสั้นและตอบได้จากข้อความจริงเท่านั้น
ตอบเป็น JSON เท่านั้น:
{{
  "question": "...",
  "answer": "...",
  "hint": "...",
  "evidence_terms": ["คำสำคัญ1", "คำสำคัญ2"]
}}"""

    raw = await gemini.generate_content(prompt=prompt, temperature=0.3)

    import json
    import re

    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise HTTPException(status_code=500, detail="Failed to parse generated quiz")

    payload = json.loads(m.group(0))
    return {
        "book_id": book_id,
        "book_title": book.get("title", "Untitled Book"),
        "question": payload.get("question", ""),
        "answer": payload.get("answer", ""),
        "hint": payload.get("hint", ""),
        "evidence_terms": payload.get("evidence_terms", []),
    }


@router.post("/attempt")
async def save_quiz_attempt(
    attempt: QuizAttempt,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Save quiz attempt to database"""
    try:
        attempt_dict = attempt.model_dump()
        result = await db.quiz_attempts.insert_one(attempt_dict)
        
        return {
            "id": str(result.inserted_id),
            "message": "Quiz attempt saved successfully"
        }
    except Exception as e:
        logger.error(f"Failed to save quiz attempt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=QuizHistoryResponse)
async def get_quiz_history(
    category: Optional[str] = Query(None, description="Filter by node type"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get quiz history and statistics"""
    try:
        # Build query filter
        query_filter = {}
        if category and category != "all":
            query_filter["node_type"] = category
        
        # Get recent attempts
        cursor = db.quiz_attempts.find(query_filter).sort("created_at", -1).limit(limit)
        attempts = await cursor.to_list(length=limit)
        
        # Convert to response models
        recent_attempts = []
        for attempt in attempts:
            attempt["_id"] = str(attempt["_id"])
            recent_attempts.append(QuizAttemptInDB(**attempt))
        
        # Calculate statistics
        total_attempts = len(recent_attempts)
        correct_count = sum(1 for a in recent_attempts if a.is_correct)
        incorrect_count = total_attempts - correct_count
        accuracy = (correct_count / total_attempts * 100) if total_attempts > 0 else 0
        
        # Stats by category
        by_category = {}
        for attempt in recent_attempts:
            cat = attempt.node_type
            if cat not in by_category:
                by_category[cat] = {"correct": 0, "total": 0}
            by_category[cat]["total"] += 1
            if attempt.is_correct:
                by_category[cat]["correct"] += 1
        
        return QuizHistoryResponse(
            total_attempts=total_attempts,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            accuracy=accuracy,
            recent_attempts=recent_attempts,
            by_category=by_category,
        )
    
    except Exception as e:
        logger.error(f"Failed to get quiz history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_quiz_categories(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get available quiz categories (node types)"""
    try:
        # Get distinct node types from nodes collection
        node_types = await db.nodes.distinct("type")
        
        # Get count for each category
        categories = []
        for node_type in node_types:
            count = await db.nodes.count_documents({"type": node_type})
            categories.append({
                "type": node_type,
                "count": count
            })
        
        # Sort by count descending
        categories.sort(key=lambda x: x["count"], reverse=True)
        
        return {
            "categories": categories,
            "total_nodes": sum(c["count"] for c in categories)
        }
    
    except Exception as e:
        logger.error(f"Failed to get quiz categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_quiz_stats(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Get overall quiz statistics"""
    try:
        total_attempts = await db.quiz_attempts.count_documents({})
        
        if total_attempts == 0:
            return {
                "total_attempts": 0,
                "correct_count": 0,
                "incorrect_count": 0,
                "accuracy": 0,
                "by_category": {}
            }
        
        # Aggregate statistics
        pipeline = [
            {
                "$group": {
                    "_id": "$node_type",
                    "total": {"$sum": 1},
                    "correct": {"$sum": {"$cond": ["$is_correct", 1, 0]}}
                }
            }
        ]
        
        cursor = db.quiz_attempts.aggregate(pipeline)
        category_stats = await cursor.to_list(length=None)
        
        by_category = {}
        total_correct = 0
        for stat in category_stats:
            cat = stat["_id"]
            by_category[cat] = {
                "correct": stat["correct"],
                "total": stat["total"],
                "accuracy": (stat["correct"] / stat["total"] * 100) if stat["total"] > 0 else 0
            }
            total_correct += stat["correct"]
        
        return {
            "total_attempts": total_attempts,
            "correct_count": total_correct,
            "incorrect_count": total_attempts - total_correct,
            "accuracy": (total_correct / total_attempts * 100) if total_attempts > 0 else 0,
            "by_category": by_category
        }
    
    except Exception as e:
        logger.error(f"Failed to get quiz stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history")
async def clear_quiz_history(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Clear all quiz history (for testing)"""
    try:
        result = await db.quiz_attempts.delete_many({})
        return {
            "message": "Quiz history cleared",
            "deleted_count": result.deleted_count
        }
    except Exception as e:
        logger.error(f"Failed to clear quiz history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

"""Analytics API for Query Logs"""

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
from datetime import datetime, timedelta
from collections import Counter

from app.db.mongodb import get_db

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/queries/stats")
async def get_query_stats(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get query statistics for the last N days"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    start_timestamp = start_date.timestamp()
    
    # Get all queries in the time period
    cursor = db.query_logs.find({
        "timestamp": {"$gte": start_timestamp}
    }).sort("timestamp", -1)
    
    queries = await cursor.to_list(length=None)
    
    if not queries:
        return {
            "total_queries": 0,
            "avg_response_time_ms": 0,
            "avg_sources_per_query": 0,
            "avg_nodes_explored": 0,
            "time_range_days": days
        }
    
    # Calculate statistics
    total_queries = len(queries)
    avg_response_time = sum(q.get("query_time_ms", 0) for q in queries) / total_queries
    avg_sources = sum(q.get("num_sources", 0) for q in queries) / total_queries
    avg_nodes = sum(len(q.get("nodes_explored", [])) for q in queries) / total_queries
    
    return {
        "total_queries": total_queries,
        "avg_response_time_ms": round(avg_response_time, 2),
        "avg_sources_per_query": round(avg_sources, 2),
        "avg_nodes_explored": round(avg_nodes, 2),
        "time_range_days": days,
        "period_start": start_date.isoformat(),
        "period_end": datetime.utcnow().isoformat()
    }


@router.get("/queries/popular")
async def get_popular_queries(
    limit: int = Query(default=10, ge=1, le=50),
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get most popular queries (by query hash)"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    start_timestamp = start_date.timestamp()
    
    # Aggregate by query hash
    pipeline = [
        {"$match": {"timestamp": {"$gte": start_timestamp}}},
        {"$group": {
            "_id": "$query_hash",
            "count": {"$sum": 1},
            "query_sample": {"$first": "$query"},
            "avg_time_ms": {"$avg": "$query_time_ms"},
            "avg_sources": {"$avg": "$num_sources"}
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit}
    ]
    
    results = await db.query_logs.aggregate(pipeline).to_list(length=None)
    
    popular_queries = [
        {
            "query": r["query_sample"],
            "times_asked": r["count"],
            "avg_response_time_ms": round(r["avg_time_ms"], 2),
            "avg_sources": round(r["avg_sources"], 2)
        }
        for r in results
    ]
    
    return {
        "popular_queries": popular_queries,
        "time_range_days": days
    }


@router.get("/queries/recent")
async def get_recent_queries(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get recent queries with details"""
    
    cursor = db.query_logs.find().sort("timestamp", -1).limit(limit)
    queries = await cursor.to_list(length=None)
    
    recent = [
        {
            "query": q["query"],
            "starting_nodes": q.get("starting_nodes", []),
            "nodes_explored_count": len(q.get("nodes_explored", [])),
            "num_sources": q.get("num_sources", 0),
            "response_time_ms": q.get("query_time_ms", 0),
            "timestamp": datetime.fromtimestamp(q["timestamp"]).isoformat()
        }
        for q in queries
    ]
    
    return {"recent_queries": recent}


@router.get("/queries/slow")
async def get_slow_queries(
    threshold_ms: float = Query(default=5000, ge=100, le=60000),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get queries that took longer than threshold"""
    
    cursor = db.query_logs.find({
        "query_time_ms": {"$gte": threshold_ms}
    }).sort("query_time_ms", -1).limit(limit)
    
    slow_queries = await cursor.to_list(length=None)
    
    results = [
        {
            "query": q["query"],
            "response_time_ms": q.get("query_time_ms", 0),
            "nodes_explored_count": len(q.get("nodes_explored", [])),
            "num_sources": q.get("num_sources", 0),
            "timestamp": datetime.fromtimestamp(q["timestamp"]).isoformat()
        }
        for q in slow_queries
    ]
    
    return {
        "slow_queries": results,
        "threshold_ms": threshold_ms,
        "count": len(results)
    }


@router.delete("/queries/logs")
async def clear_query_logs(
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Clear all query logs (for testing/maintenance)"""
    
    result = await db.query_logs.delete_many({})
    
    return {
        "message": "Query logs cleared",
        "deleted_count": result.deleted_count
    }

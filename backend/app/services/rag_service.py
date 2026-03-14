"""RAG Service - Graph Retrieval Augmented Generation"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Any, Set, Tuple
from collections import deque
import time
import logging
import re  # For regex pattern matching in relationship filtering
from bson import ObjectId

from app.models import QueryRequest, QueryResponse, QueryStep, BFSResult
from app.services.embedding_service import get_embedding_service
from app.services.gemini_service import get_gemini_service
from app.db.vector_db import vector_db

logger = logging.getLogger(__name__)


class RAGService:
    """
    Graph RAG Service implementing:
    1. Dense Retrieval (Karpukhin et al., 2020)
    2. BFS Traversal (Goldberg, 2005)
    3. Entity Matching (Mudgal et al., 2018)
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.nodes_collection = db.nodes
        self.links_collection = db.links
        self.query_logs_collection = db.query_logs
        
        self.embedding_service = get_embedding_service()
        self.gemini_service = get_gemini_service()
        self.vector_db = vector_db
    
    async def query_graph(self, query_request: QueryRequest) -> QueryResponse:
        """
        Execute graph query using RELATIONSHIP-AWARE GraphRAG pipeline
        
        Pipeline:
        1. Query Analysis: ใช้ Gemini วิเคราะห์ query เพื่อเข้าใจ intent และ relationship patterns
        2. Dense Retrieval: หา starting nodes + relevant relationships
        3. Smart BFS: Traverse เฉพาะ relationships ที่เกี่ยวข้อง
        4. Relationship-Rich Context: สร้าง context ที่มีข้อมูลความสัมพันธ์
        5. Answer Generation: Generate คำตอบจากบริบทที่สมบูรณ์
        """
        start_time = time.time()
        execution_steps = []
        query = query_request.query
        
        logger.info(f"🔍 Query: {query}")
        
        # ========================
        # STEP 0: QUERY ANALYSIS (NEW!)
        # ========================
        step_start = time.time()
        
        query_analysis = await self._analyze_query_intent(query)
        
        execution_steps.append(QueryStep(
            step_number=0,
            step_type="query_analysis",
            description=f"Query Analysis: {query_analysis['intent_type']}",
            nodes_involved=[],
            timestamp=time.time() - step_start,
        ))
        
        logger.info(f"📊 Query Intent: {query_analysis['intent_type']}, Target Relationships: {query_analysis['relationship_keywords']}")
        
        # Adjust max_hops based on query complexity (NEW!)
        num_entities = len(query_analysis.get('entities', []))
        if num_entities >= 2 and query_analysis['intent_type'] == 'relationship':
            # Multi-entity relationship query → increase hops
            adjusted_max_hops = min(query_request.max_hops + 1, 5)
            logger.info(f"🔄 Multi-entity query detected, increasing max_hops: {query_request.max_hops} → {adjusted_max_hops}")
        else:
            adjusted_max_hops = query_request.max_hops
        
        # ========================
        # STEP 1: RELATIONSHIP-AWARE DENSE RETRIEVAL
        # ========================
        step_start = time.time()

        # Book-first memory model: start from relevant books, then drill down to nodes
        book_first_node_ids = await self._book_first_retrieval(query)
        
        starting_node_ids = await self._relationship_aware_retrieval(
            query=query,
            query_analysis=query_analysis,
            top_k=query_request.top_k,
        )

        if book_first_node_ids:
            merged = []
            seen = set()
            for nid in book_first_node_ids + starting_node_ids:
                if nid in seen:
                    continue
                seen.add(nid)
                merged.append(nid)
            starting_node_ids = merged[: max(query_request.top_k * 2, query_request.top_k)]
        
        execution_steps.append(QueryStep(
            step_number=1,
            step_type="dense_retrieval",
            description=f"Relationship-Aware Retrieval: Found {len(starting_node_ids)} starting nodes",
            nodes_involved=starting_node_ids,
            timestamp=time.time() - step_start,
        ))
        
        if not starting_node_ids:
            logger.warning("❌ No starting nodes found")
            return QueryResponse(
                answer="ไม่พบข้อมูลที่เกี่ยวข้องกับคำถามของคุณ",
                sources=[],
                execution_steps=execution_steps,
                nodes_explored=[],
                query_time_ms=(time.time() - start_time) * 1000,
            )
        
        # ========================
        # STEP 2: SMART BFS WITH RELATIONSHIP FILTERING
        # ========================
        step_start = time.time()
        
        bfs_result = await self._smart_bfs_with_relationships(
            starting_nodes=starting_node_ids,
            max_hops=adjusted_max_hops,  # ✅ Use adjusted value
            query_analysis=query_analysis,
        )
        
        execution_steps.append(QueryStep(
            step_number=2,
            step_type="bfs_traversal",
            description=f"Smart BFS: Explored {len(bfs_result.visited_nodes)} nodes, {len(bfs_result.paths)} relevant paths",
            nodes_involved=bfs_result.visited_nodes,
            timestamp=time.time() - step_start,
        ))
        
        # ========================
        # STEP 3: ANSWER GENERATION
        # ========================
        step_start = time.time()
        
        # Get nodes with relationship context
        nodes_data = await self._get_nodes_by_ids(bfs_result.context_node_ids)
        sources = [node["label"] for node in nodes_data]
        all_nodes_data = await self._get_nodes_by_ids(bfs_result.visited_nodes)
        
        # Generate answer using Gemini with relationship-rich context
        answer = await self.gemini_service.generate_answer(
            query=query,
            context=bfs_result.context,
            sources=sources,
        )
        
        execution_steps.append(QueryStep(
            step_number=3,
            step_type="summary_generation",
            description=f"Generated answer from {len(sources)} sources with relationship context",
            nodes_involved=[],
            timestamp=time.time() - step_start,
        ))
        
        # ========================
        # STEP 4: LOG QUERY
        # ========================
        query_time_ms = (time.time() - start_time) * 1000
        
        await self._log_query(
            query=query,
            starting_nodes=starting_node_ids,
            nodes_explored=bfs_result.visited_nodes,
            sources=sources,
            query_time_ms=query_time_ms,
        )

        # Reinforce recalled memories (nodes and traversed links)
        await self._apply_spreading_activation(
            visited_node_ids=bfs_result.visited_nodes,
            paths=bfs_result.paths,
        )
        
        logger.info(f"✅ Query completed in {query_time_ms:.2f}ms")
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            execution_steps=execution_steps,
            nodes_explored=[{"id": str(n["_id"]), "label": n["label"]} for n in all_nodes_data],
            bfs_result=bfs_result,
            query_time_ms=query_time_ms,
        )

    async def _book_first_retrieval(self, query: str) -> List[str]:
        """
        Human-like retrieval: search books first, then use their node_ids as anchors.
        """
        try:
            keywords = [k for k in query.lower().split() if len(k) > 1]
            if not keywords:
                return []

            regex = "|".join([re.escape(k) for k in keywords])
            books = await self.db.books.find(
                {
                    "$or": [
                        {"title": {"$regex": regex, "$options": "i"}},
                        {"full_text": {"$regex": regex, "$options": "i"}},
                    ]
                }
            ).sort("updated_at", -1).to_list(length=20)

            node_ids = []
            for b in books:
                node_ids.extend([str(nid) for nid in b.get("node_ids", [])])

            # Deduplicate while preserving order
            dedup = []
            seen = set()
            for nid in node_ids:
                if nid in seen:
                    continue
                seen.add(nid)
                dedup.append(nid)

            if dedup:
                logger.info(f"📚 Book-first retrieval anchors: {len(dedup)} nodes")

            return dedup[:12]
        except Exception as e:
            logger.debug(f"Book-first retrieval skipped: {e}")
            return []
    
    # =========================
    # NEW: RELATIONSHIP-AWARE METHODS
    # =========================
    
    async def _analyze_query_intent(self, query: str) -> dict:
        """
        ใช้ Gemini วิเคราะห์ query เพื่อเข้าใจ:
        - Intent type (factual, relationship, navigation, comparison)
        - Target entities
        - Relationship keywords ที่น่าจะเกี่ยวข้อง
        """
        analysis_prompt = f"""วิเคราะห์คำถามต่อไปนี้และระบุ:

คำถาม: "{query}"

ให้ตอบเป็น JSON format:
{{
  "intent_type": "<factual|relationship|navigation|comparison>",
  "entities": ["entity1", "entity2"],
  "relationship_keywords": ["keyword1", "keyword2"],
  "explanation": "คำอธิบายสั้นๆ"
}}

ตัวอย่าง:
- "NVIDIA ผลิตอะไร?" → intent: relationship, entities: ["NVIDIA"], keywords: ["ผลิต", "produces", "manufactures", "makes"]
- "Jensen Huang เป็นใคร?" → intent: factual, entities: ["Jensen Huang"], keywords: ["เป็น", "is", "role", "position"]
- "ความสัมพันธ์ระหว่าง NVIDIA กับ AI?" → intent: relationship, entities: ["NVIDIA", "AI"], keywords: ["สัมพันธ์", "relates", "connection", "works with"]

เน้น: ให้ keyword ที่หลากหลายทั้งภาษาไทยและอังกฤษ (เพราะ relationship labels อาจเป็นภาษาใดก็ได้)"""
        
        try:
            response = await self.gemini_service.generate_content(analysis_prompt)
            
            # Parse JSON response
            import json
            import re
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                json_str = json_match.group(0) if json_match else '{}'
            
            analysis = json.loads(json_str)
            logger.info(f"📊 Query Analysis: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}, using defaults")
            return {
                "intent_type": "factual",
                "entities": [],
                "relationship_keywords": [],
                "explanation": "Analysis failed, using default"
            }
    
    async def _relationship_aware_retrieval(
        self, 
        query: str, 
        query_analysis: dict, 
        top_k: int = 2
    ) -> List[str]:
        """
        Dense Retrieval ที่คำนึงถึง Relationships
        
        Strategy:
        1. Vector search สำหรับ nodes
        2. หา links ที่มี labels ตรงกับ relationship_keywords
        3. รวมโหนดที่เชื่อมโยงด้วย relationships ที่เกี่ยวข้อง
        """
        # Stage 1: Standard vector search
        node_ids = await self._dense_retrieval(query, top_k)
        
        if not node_ids:
            return []
        
        # Stage 2: Find related nodes via relevant relationships
        relationship_keywords = query_analysis.get("relationship_keywords", [])
        
        if not relationship_keywords:
            logger.info("⚠️ No relationship keywords, using standard retrieval")
            return node_ids  # No relationship filtering
        
        logger.info(f"🔗 Searching for relationships: {relationship_keywords}")
        
        # Build regex pattern for relationship labels
        pattern = "|".join([re.escape(kw) for kw in relationship_keywords])
        
        # Find links with matching relationship labels OR links without labels (fallback)
        matching_links = await self.links_collection.find({
            "$or": [
                {"label": {"$regex": pattern, "$options": "i"}},
                {"labelReverse": {"$regex": pattern, "$options": "i"}},
                # FALLBACK: Include links with empty/null labels
                {"label": {"$in": [None, "", "relates_to", "เกี่ยวข้องกับ"]}},
                {"labelReverse": {"$in": [None, "", "relates_to", "เกี่ยวข้องกับ"]}},
            ]
        }).to_list(length=200)  # Increase limit for fallback
        
        logger.info(f"🔗 Found {len(matching_links)} links (including unlabeled)")
        
        # Collect nodes connected by these relationships
        related_node_ids = set(node_ids)
        for link in matching_links:
            source = str(link["source"])
            target = str(link["target"])
            
            # If either end is in our starting nodes, add the other end
            if source in node_ids:
                related_node_ids.add(target)
            if target in node_ids:
                related_node_ids.add(source)
        
        expanded_ids = list(related_node_ids)[:top_k * 2]  # Expand but limit
        logger.info(f"✅ Expanded from {len(node_ids)} to {len(expanded_ids)} nodes via relationships")
        
        return expanded_ids
    
    async def _smart_bfs_with_relationships(
        self,
        starting_nodes: List[str],
        max_hops: int,
        query_analysis: dict,
    ) -> BFSResult:
        """
        Smart BFS ที่ filter relationships based on relevance
        
        แทนที่จะ traverse ทุก link แบบสุ่ม:
        1. ดึง links พร้อม labels
        2. Score ความเกี่ยวข้องของ relationship label กับ query
        3. Traverse เฉพาะ paths ที่มี score สูง
        4. สร้าง context ที่บอกความสัมพันธ์ชัดเจน
        """
        visited_nodes = set(starting_nodes)
        context_parts = []
        context_node_ids = []
        paths = []  # Store paths as List[List[str]]
        
        # Get starting nodes content
        start_nodes_data = await self._get_nodes_by_ids(starting_nodes)
        
        for node in start_nodes_data:
            label = node.get("label", "")
            content = node.get("content", "")
            context_parts.append(f"**{label}**: {content}")
            context_node_ids.append(str(node["_id"]))
        
        # Multi-hop traversal
        current_layer = starting_nodes
        
        for hop in range(max_hops):
            if not current_layer:
                break
            
            logger.info(f"🔄 Hop {hop + 1}: Exploring {len(current_layer)} nodes")
            
            # Get all links from current layer
            links = await self.links_collection.find({
                "$or": [
                    {"source": {"$in": current_layer}},
                    {"target": {"$in": current_layer}},
                ]
            }).to_list(length=1000)
            
            logger.info(f"🔗 Found {len(links)} candidate links")
            
            # Score each link by relationship relevance
            scored_links = []
            
            for link in links:
                source_id = str(link["source"])
                target_id = str(link["target"])
                
                # Determine direction
                if source_id in current_layer:
                    direction = "forward"
                    next_node = target_id
                    label = link.get("label", "relates_to")
                else:
                    direction = "backward"
                    next_node = source_id
                    label = link.get("labelReverse", "relates_to")
                
                # Skip if already visited
                if next_node in visited_nodes:
                    continue
                
                # Score relationship relevance
                relevance_score = await self._score_relationship_relevance(
                    query_analysis=query_analysis,
                    relationship_label=label,
                )
                
                scored_links.append({
                    "link": link,
                    "source": source_id,
                    "next_node": next_node,
                    "label": label,
                    "direction": direction,
                    "score": relevance_score,
                })
            
            # Sort by relevance score (highest first)
            scored_links.sort(key=lambda x: x["score"], reverse=True)
            
            # Take top N relevant relationships
            # If scores are all similar (unlabeled graph), take more links
            top_scores = [sl["score"] for sl in scored_links[:5]]
            if top_scores and max(top_scores) - min(top_scores) < 0.3:
                # Scores are similar - likely unlabeled graph, take more
                top_n = min(10, len(scored_links))
                logger.info(f"⚠️ Similar scores detected (unlabeled graph), expanding to top {top_n}")
            else:
                top_n = min(5, len(scored_links))
            
            relevant_links = scored_links[:top_n]
            
            logger.info(f"✅ Selected {len(relevant_links)} most relevant links:")
            for rl in relevant_links:
                logger.info(f"   - {rl['label']} (score: {rl['score']:.3f})")
            
            # Build next layer
            next_layer = []
            
            for rl in relevant_links:
                next_node_id = rl["next_node"]
                label = rl["label"]
                source_id = rl["source"]
                
                # Get node data
                node_data = await self._get_nodes_by_ids([next_node_id])
                if not node_data:
                    continue
                
                node = node_data[0]
                node_label = node.get("label", "")
                node_content = node.get("content", "")
                
                # Add to context WITH RELATIONSHIP INFO
                relationship_context = f"**{node_label}** [{label}]: {node_content}"
                context_parts.append(relationship_context)
                context_node_ids.append(next_node_id)
                
                # Track path as [source, target]
                paths.append([source_id, next_node_id])
                
                visited_nodes.add(next_node_id)
                next_layer.append(next_node_id)
            
            current_layer = next_layer
        
        # Build relationship path summary (NEW!)
        if paths:
            path_summary = "\n📍 **Relationship Paths Found:**\n"
            
            # Group paths by depth
            for i, path in enumerate(paths[:10], 1):  # Show top 10 paths
                source_id, target_id = path
                
                # Get node labels
                source_node = await self._get_nodes_by_ids([source_id])
                target_node = await self._get_nodes_by_ids([target_id])
                
                if source_node and target_node:
                    source_label = source_node[0].get("label", "?")
                    target_label = target_node[0].get("label", "?")
                    
                    # Find relationship label from links
                    link = await self.links_collection.find_one({
                        "source": source_id,
                        "target": target_id
                    })
                    
                    if link:
                        rel_label = link.get("label", "relates_to")
                    else:
                        # Try reverse direction
                        link = await self.links_collection.find_one({
                            "source": target_id,
                            "target": source_id
                        })
                        rel_label = link.get("labelReverse", "relates_to") if link else "relates_to"
                    
                    path_summary += f"{i}. **{source_label}** --[{rel_label}]--> **{target_label}**\n"
            
            # Prepend path summary to context
            context = path_summary + "\n\n📄 **Detailed Information:**\n\n" + "\n\n".join(context_parts)
        else:
            context = "\n\n".join(context_parts)
        
        logger.info(f"📊 BFS Result: {len(visited_nodes)} nodes, {len(paths)} paths")
        
        return BFSResult(
            visited_nodes=list(visited_nodes),
            context=context,
            context_node_ids=context_node_ids,
            max_depth_reached=max_hops,
            paths=paths,
        )
    
    async def _score_relationship_relevance(
        self,
        query_analysis: dict,
        relationship_label: str,
    ) -> float:
        """
        Score ความเกี่ยวข้องของ relationship label กับ query
        
        Returns: 0.0 to 1.0 (higher = more relevant)
        """
        # Handle empty/null labels (FALLBACK for unlabeled graphs)
        if not relationship_label or relationship_label in ["", "relates_to", "related"]:
            logger.debug("Empty label, using neutral score 0.6")
            return 0.6  # Neutral score - still traverse but lower priority
        
        # Simple keyword matching (fast)
        relationship_keywords = query_analysis.get("relationship_keywords", [])
        
        if not relationship_keywords:
            return 0.6  # Neutral score if no keywords
        
        # Exact match
        for keyword in relationship_keywords:
            if keyword.lower() in relationship_label.lower():
                return 1.0  # Perfect match
        
        # Partial match (fuzzy)
        label_words = set(relationship_label.lower().split())
        keyword_words = set(" ".join(relationship_keywords).lower().split())
        
        overlap = len(label_words & keyword_words)
        if overlap > 0:
            return 0.7 + (overlap * 0.1)  # Boost for each matching word
        
        # TODO: Use Gemini for semantic matching (slower but more accurate)
        # For now, default relevance
        return 0.4  # Low but not zero

    async def _apply_spreading_activation(
        self,
        visited_node_ids: List[str],
        paths: List[List[str]],
    ):
        """
        Human-like recall reinforcement:
        - frequently visited nodes get higher memory_strength
        - traversed links get higher synaptic_weight
        """
        now = time.time()

        for node_id in set(visited_node_ids):
            try:
                node_filter = {"_id": ObjectId(node_id)} if ObjectId.is_valid(node_id) else {"_id": node_id}
                await self.nodes_collection.update_one(
                    node_filter,
                    {
                        "$inc": {
                            "metadata.activation_count": 1,
                            "metadata.memory_strength": 0.05,
                        },
                        "$set": {
                            "metadata.last_activated_at": now,
                        },
                    },
                )
            except Exception as e:
                logger.debug(f"Node activation update skipped for {node_id}: {e}")

        for path in paths:
            if len(path) < 2:
                continue
            source_id, target_id = path[0], path[1]
            try:
                await self.links_collection.update_one(
                    {
                        "$or": [
                            {"source": source_id, "target": target_id},
                            {"source": target_id, "target": source_id},
                        ]
                    },
                    {
                        "$inc": {
                            "metadata.activation_count": 1,
                            "metadata.synaptic_weight": 0.1,
                        },
                        "$set": {
                            "metadata.last_activated_at": now,
                        },
                    },
                )
            except Exception as e:
                logger.debug(f"Link activation update skipped for {source_id}->{target_id}: {e}")
    
    async def _dense_retrieval(self, query: str, top_k: int = 2) -> List[str]:
        """
        Dense Retrieval using vector similarity search + Fuzzy Matching
        
        Strategy: Multi-stage fallback for maximum recall
        1. Vector search (threshold 0.35 - ลดลงจาก 0.6)
        2. Fuzzy text matching (MongoDB regex)
        3. Gemini semantic matching (last resort)
        """
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.encode(query)
            
            # Stage 1: Vector search with LOWER threshold for better recall
            results = await self.vector_db.search_similar(
                query_embedding=query_embedding,
                top_k=top_k * 3,  # Get more candidates
                score_threshold=0.35,  # ลดจาก 0.6 → 0.35 เพื่อเพิ่ม recall
            )
            
            # Log similarity scores
            if results:
                scores = [f"{r['payload']['label']}: {r['score']:.3f}" for r in results]
                logger.info(f"Vector Search: {', '.join(scores[:5])}")
            
            node_ids = [result["id"] for result in results]
            
            if len(node_ids) >= top_k:
                logger.info(f"✅ Vector search: Found {len(node_ids)} nodes")
                return node_ids[:top_k]
            
            # Stage 2: Fuzzy text matching (keyword-based)
            logger.info(f"⚠️ Only {len(node_ids)} vector results, trying fuzzy matching...")
            fuzzy_ids = await self._fuzzy_text_search(query, top_k)
            
            # Merge results (deduplicate)
            combined = node_ids + [fid for fid in fuzzy_ids if fid not in node_ids]
            
            if len(combined) >= top_k:
                logger.info(f"✅ Combined search: Found {len(combined)} nodes")
                return combined[:top_k]
            
            # Stage 3: Gemini semantic matching (expensive, last resort)
            logger.warning(f"⚠️ Insufficient results ({len(combined)}), using Gemini...")
            gemini_ids = await self._gemini_semantic_search(query, top_k)
            
            final = combined + [gid for gid in gemini_ids if gid not in combined]
            return final[:top_k] if final else []
        
        except Exception as e:
            logger.error(f"Dense retrieval failed: {e}")
            return await self._fuzzy_text_search(query, top_k)
    
    async def _fuzzy_text_search(self, query: str, top_k: int) -> List[str]:
        """
        Fuzzy text matching using MongoDB regex (รองรับพิมพ์ผิด, คำใกล้เคียง)
        """
        try:
            # Normalize query (remove spaces, lowercase)
            normalized_query = query.lower().strip()
            
            # Split into keywords
            keywords = normalized_query.split()
            
            # Build regex patterns (case-insensitive, partial match)
            regex_patterns = []
            for keyword in keywords:
                if len(keyword) >= 2:  # Ignore single chars
                    # Allow 1 char difference for fuzzy matching
                    regex_patterns.append({"$or": [
                        {"label": {"$regex": keyword, "$options": "i"}},
                        {"content": {"$regex": keyword, "$options": "i"}}
                    ]})
            
            if not regex_patterns:
                return []
            
            # Find nodes matching ANY keyword
            cursor = self.nodes_collection.find(
                {"$or": regex_patterns}
            ).limit(top_k * 2)
            
            nodes = await cursor.to_list(None)
            node_ids = [str(node["_id"]) for node in nodes]
            
            if node_ids:
                logger.info(f"✅ Fuzzy search: Found {len(node_ids)} nodes")
            
            return node_ids[:top_k]
        
        except Exception as e:
            logger.error(f"Fuzzy search failed: {e}")
            return []
    
    async def _gemini_semantic_search(self, query: str, top_k: int) -> List[str]:
        """
        Gemini semantic matching (token-expensive, last resort)
        """
        try:
            # Get sample nodes (limit to 50 for token efficiency)
            cursor = self.nodes_collection.find().limit(50)
            nodes = await cursor.to_list(None)
            
            if not nodes:
                return []
            
            node_dicts = [
                {"id": str(node["_id"]), "label": node["label"], "content": node.get("content", "")[:100]}
                for node in nodes
            ]
            
            # Use Gemini for semantic matching
            node_ids = await self.gemini_service.dense_retrieval(query, node_dicts, top_k)
            
            if node_ids:
                logger.info(f"✅ Gemini search: Found {len(node_ids)} nodes")
            
            return node_ids
        
        except Exception as e:
            logger.error(f"Gemini search failed: {e}")
            return []
    
    async def _dense_retrieval_fallback(self, query: str, top_k: int) -> List[str]:
        """
        Fallback dense retrieval - OPTIMIZED VERSION
        
        ⚠️ OLD METHOD: ดึง ALL nodes จาก MongoDB แล้วส่งให้ Gemini (ช้ามาก!)
        ✅ NEW METHOD: ใช้ vector search ที่ threshold ต่ำกว่า แล้ว fallback เป็น keyword matching
        
        เหตุผล: Gemini dense retrieval ใช้ token สูง + ช้า เมื่อ nodes เยอะ
        """
        logger.info("⚡ Using optimized fallback: Lower threshold vector search")
        
        try:
            # Try vector search with lower threshold (0.3 instead of 0.6)
            query_embedding = await self.embedding_service.encode(query)
            results = await self.vector_db.search_similar(
                query_embedding=query_embedding,
                top_k=top_k * 2,
                score_threshold=0.3,  # Lower threshold for fallback
            )
            
            if results:
                node_ids = [result["id"] for result in results]
                logger.info(f"✅ Fallback vector search: Found {len(node_ids)} nodes (threshold 0.3)")
                return node_ids[:top_k]
            
            # If still no results, use keyword matching (fast)
            logger.warning("⚠️ No vector results, using keyword matching")
            return await self._keyword_matching(query, top_k)
        
        except Exception as e:
            logger.error(f"Fallback retrieval failed: {e}")
            return await self._keyword_matching(query, top_k)
    
    async def _keyword_matching(self, query: str, top_k: int) -> List[str]:
        """
        Enhanced keyword matching with fuzzy search and Thai support
        
        Scoring strategy:
        1. Exact label match: 100 points
        2. Label contains query: 50 points
        3. Query contains label: 40 points
        4. Fuzzy match (>0.8 similarity): 30 points
        5. Keyword in label: 5 points each
        6. Keyword in content: 2 points each
        """
        from difflib import SequenceMatcher
        
        query_lower = query.lower()
        keywords = query_lower.split()
        
        nodes = await self.nodes_collection.find().to_list(None)
        
        scored_nodes = []
        for node in nodes:
            label_lower = node["label"].lower()
            content_lower = node.get("content", "").lower()
            score = 0
            
            # 1. Exact match (highest priority)
            if label_lower == query_lower:
                score += 100
            
            # 2. Label contains entire query
            if query_lower in label_lower:
                score += 50
            
            # 3. Query contains entire label
            if label_lower in query_lower:
                score += 40
            
            # 4. Fuzzy string matching (similar words)
            similarity = SequenceMatcher(None, query_lower, label_lower).ratio()
            if similarity > 0.8:
                score += int(30 * similarity)
            
            # 5. Check each keyword
            for keyword in keywords:
                # Skip very short keywords (noise words)
                if len(keyword) <= 2:
                    continue
                
                # Exact keyword in label (weighted heavily)
                if keyword in label_lower:
                    score += 5
                
                # Fuzzy match for each keyword
                for word in label_lower.split():
                    word_similarity = SequenceMatcher(None, keyword, word).ratio()
                    if word_similarity > 0.75:  # 75% similar
                        score += int(3 * word_similarity)
                
                # Keyword in content (lower weight)
                if keyword in content_lower:
                    score += 2
            
            if score > 0:
                scored_nodes.append((str(node["_id"]), score))
        
        # Sort by score (highest first)
        scored_nodes.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"🔍 Keyword matching: {len(scored_nodes)} nodes scored, top: {scored_nodes[:3] if scored_nodes else 'none'}")
        
        return [node_id for node_id, _ in scored_nodes[:top_k]]
    async def _bfs_traversal(
        self,
        starting_nodes: List[str],
        max_hops: int = 3,
    ) -> BFSResult:
        """
        Bidirectional BFS Traversal to explore graph neighborhood 
        using MongoDB's native $graphLookup for optimal performance.
        """
        # Track all findings
        visited_nodes: Set[str] = set()
        paths: List[List[str]] = []
        context_parts: List[str] = []
        context_node_ids: List[str] = []
        max_depth_reached = 0

        # Convert string IDs to ObjectIds where appropriate for starting nodes
        start_oids = []
        for sid in starting_nodes:
            try:
                 start_oids.append(ObjectId(sid))
            except Exception:
                 start_oids.append(sid)
                 
        for start_id in start_oids:
            start_id_str = str(start_id)
            if start_id_str not in visited_nodes:
                visited_nodes.add(start_id_str)
                # Fetch starting node for context
                start_node = await self.nodes_collection.find_one({"_id": start_id})
                if start_node:
                     context_parts.append(f"**{start_node.get('label', '')}**: {start_node.get('content', '')}")
                     context_node_ids.append(start_id_str)
            
            # Use MongoDB Aggregation for efficient recursive lookup
            pipeline = [
                {"$match": {"_id": start_id}},
                {"$graphLookup": {
                    "from": "links",          # Collection to lookup
                    "startWith": start_id_str,    # Which value to start connecting from
                    # In a directed graph we might check just 'source' to 'target', 
                    # but for bidirectional graph traversal we can use 'source' connecting to both
                    # Or we check BOTH directions. A simple robust graphLookup on links
                    # To do bidirectional perfectly in one pass we'd need a secondary collection or combined fields.
                    # Since links have source/target, let's look up links where source or target matches.
                    # As $graphLookup doesn't perfectly support OR conditions in connectToField, it's common to traverse outward,
                    # but we can query links directly.
                    # For absolute best bidirectional, 2 separate graphLookups (forward and backward) are often used.
                    
                    # Forward traversal (outgoing edges):
                    "connectFromField": "target",
                    "connectToField": "source",
                    "as": "outgoing_path",
                    "maxDepth": max_hops - 1,   # depth 0 is neighbors, so max=max_hops-1
                    "depthField": "hop_depth"
                }},
                {"$graphLookup": {
                    "from": "links",
                    "startWith": start_id_str,
                    "connectFromField": "source",
                    "connectToField": "target",
                    "as": "incoming_path",
                    "maxDepth": max_hops - 1,
                    "depthField": "hop_depth"
                }}
            ]
            
            result_cursor = self.nodes_collection.aggregate(pipeline)
            results = await result_cursor.to_list(None)
            
            if not results:
                continue
                
            result = results[0]
            
            # Process connections discovered
            all_links = result.get("outgoing_path", []) + result.get("incoming_path", [])
            
            for link in all_links:
                depth = link.get("hop_depth", 0) + 1  # 0-indexed in Mongo
                max_depth_reached = max(max_depth_reached, depth)
                
                # We reached these via the start_id. 
                source_id = str(link.get("source"))
                target_id = str(link.get("target"))
                
                if source_id not in visited_nodes:
                    visited_nodes.add(source_id)
                    paths.append([start_id_str, source_id])
                if target_id not in visited_nodes:
                    visited_nodes.add(target_id)
                    paths.append([start_id_str, target_id])
                    
        # Now fetch nodes that are in our context range (depth 1 which means immediate neighbors)
        # Visited nodes already contains all neighbors up to max_hops.
        # But for RAG context, we want details of immediate neighbors or all visited depending on rules.
        # The previous code added nodes to context if depth <= 1!
        # Because we only have links so far, let's fetch the nodes that partook.
        
        nodes_to_fetch = []
        for vid in visited_nodes:
             if vid not in context_node_ids:
                 try:
                     nodes_to_fetch.append(ObjectId(vid))
                 except Exception:
                     nodes_to_fetch.append(vid)
                     
        if nodes_to_fetch:
            neighbor_nodes = await self.nodes_collection.find({"_id": {"$in": nodes_to_fetch}}).to_list(None)
            for n_node in neighbor_nodes:
                 # To strictly match previous logic: "add to context if depth <= 1"
                 # $graphLookup hop_depth 0 means immediate neighbor (depth 1 total)
                 # So all immediate neighbors from the lookup are depth 1.
                 # Let's add them to context:
                 nid_str = str(n_node["_id"])
                 context_parts.append(f"**{n_node.get('label', '')}**: {n_node.get('content', '')}")
                 context_node_ids.append(nid_str)
        
        context = "\n\n".join(context_parts)
        
        return BFSResult(
            visited_nodes=list(visited_nodes),
            paths=paths,
            context=context,
            context_node_ids=context_node_ids,
            max_depth_reached=max_depth_reached,
        )    

    async def _get_nodes_by_ids(self, node_ids: List[str]) -> List[Dict[str, Any]]:
        """Get multiple nodes by their IDs"""
        # Convert string IDs to ObjectId
        object_ids = []
        for nid in node_ids:
            try:
                object_ids.append(ObjectId(nid) if isinstance(nid, str) else nid)
            except Exception:
                object_ids.append(nid)
        
        nodes = await self.nodes_collection.find({"_id": {"$in": object_ids}}).to_list(None)
        return nodes
    
    async def _log_query(
        self,
        query: str,
        starting_nodes: List[str],
        nodes_explored: List[str],
        sources: List[str],
        query_time_ms: float,
    ):
        """Log query for analytics"""
        try:
            log_entry = {
                "query": query,
                "query_hash": hash(query),
                "starting_nodes": starting_nodes,
                "nodes_explored": nodes_explored,
                "num_sources": len(sources),
                "query_time_ms": query_time_ms,
                "timestamp": time.time(),
            }
            
            await self.query_logs_collection.insert_one(log_entry)
        except Exception as e:
            logger.error(f"Failed to log query: {e}")
    
    async def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts
        
        Entity Matching based on: Mudgal et al. "Deep Learning for Entity Matching" (2018)
        """
        # Simple string similarity (can be enhanced with embeddings)
        t1 = text1.lower().replace(" ", "")
        t2 = text2.lower().replace(" ", "")
        
        if t1 == t2:
            return 1.0
        if t1 in t2 or t2 in t1:
            return 0.8
        
        # Use embedding similarity for better results
        try:
            embeddings = await self.embedding_service.encode([text1, text2])
            
            # Calculate cosine similarity
            import numpy as np
            emb1 = np.array(embeddings[0])
            emb2 = np.array(embeddings[1])
            
            similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            
            return float(similarity)
        
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0


def get_rag_service(db: AsyncIOMotorDatabase) -> RAGService:
    """Factory function to create RAGService instance"""
    return RAGService(db)

"""Graph Service - CRUD operations for nodes and links"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging
import re

from app.models import (
    NodeCreate,
    NodeUpdate,
    NodeResponse,
    NodeWithRelations,
    LinkCreate,
    LinkUpdate,
    LinkResponse,
    GraphData,
)
from app.services.embedding_service import get_embedding_service
from app.services.gemini_service import get_gemini_service
from app.db.vector_db import vector_db

logger = logging.getLogger(__name__)


class GraphService:
    """Service for managing graph nodes and links"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.nodes_collection = db.nodes
        self.links_collection = db.links
        self.embedding_service = get_embedding_service()
        self.gemini_service = get_gemini_service()
        self.vector_db = vector_db
    
    # ==================== HELPER METHODS ====================
    
    @staticmethod
    def calculate_similarity(s1: str, s2: str) -> float:
        """
        Calculate string similarity using simple matching (Mudgal et al., 2018)
        
        Returns:
            1.0 for exact match, 0.8 for substring match, 0.0 otherwise
        """
        a = s1.lower().replace(' ', '')
        b = s2.lower().replace(' ', '')
        
        if a == b:
            return 1.0
        if a in b or b in a:
            return 0.8
        return 0.0
    
    async def find_similar_node(self, label: str, threshold: float = 0.8) -> Optional[NodeResponse]:
        """
        Find a node with similar label (Entity Matching)
        
        Args:
            label: Label to search for
            threshold: Minimum similarity score (default 0.8)
            
        Returns:
            Most similar node if found, None otherwise
        """
        nodes = await self.get_all_nodes(limit=1000)  # Get all nodes for comparison
        
        best_match = None
        highest_similarity = 0.0
        
        for node in nodes:
            similarity = self.calculate_similarity(label, node.label)
            if similarity >= threshold and similarity > highest_similarity:
                highest_similarity = similarity
                best_match = node
        
        if best_match:
            logger.info(f"🔍 Found similar node: '{label}' → '{best_match.label}' (similarity: {highest_similarity:.2f})")
        
        return best_match
    
    async def find_similar_node_by_embedding(
        self, 
        label: str, 
        content: str = "",
        threshold: float = 0.75
    ) -> Optional[NodeResponse]:
        """
        Find similar node using vector embedding (FAST + Semantic Matching)
        
        Args:
            label: Node label
            content: Node content (optional)
            threshold: Cosine similarity threshold (default 0.75)
            
        Returns:
            Most similar node if found, None otherwise
        """
        try:
            # Generate embedding for query
            text = f"{label}. {content}"
            query_embedding = await self.embedding_service.encode(text)
            
            # Search in Qdrant (indexed, very fast)
            results = await self.vector_db.search_similar(
                query_embedding=query_embedding,
                top_k=5,  # Check top 5 candidates only
                score_threshold=threshold
            )
            
            if not results:
                return None
            
            # Get best match
            best_result = results[0]
            node_id = best_result["id"]
            similarity = best_result["score"]
            matched_label = best_result["payload"]["label"]
            
            logger.info(
                f"🔍 Vector match: '{label}' → '{matched_label}' "
                f"(similarity: {similarity:.3f})"
            )
            
            # Fetch full node data
            return await self.get_node(node_id)
            
        except Exception as e:
            logger.warning(f"Vector search failed for '{label}': {e}")
            # Fallback to string matching
            return await self.find_similar_node(label, threshold=0.85)
    
    # ==================== NODE OPERATIONS ====================
    
    async def create_node(self, node_data: NodeCreate) -> NodeResponse:
        """Create a new node — embedding generated and stored in a single DB insert"""
        node_dict = node_data.model_dump(by_alias=True)
        now = datetime.utcnow()
        node_dict["created_at"] = now
        node_dict["updated_at"] = now

        # Generate embedding BEFORE insert so we only need one DB round-trip
        try:
            text = f"{node_data.label}. {node_data.content or ''}"
            embedding = await self.embedding_service.encode(text)
            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()
            node_dict["embedding"] = embedding
        except Exception as e:
            logger.warning(f"Embedding generation failed for '{node_data.label}': {e}")

        # Single insert (embedding already inside the document)
        result = await self.nodes_collection.insert_one(node_dict)
        node_id = str(result.inserted_id)

        logger.info(f"✅ Created node: {node_id} ({node_data.label})")
        return await self.get_node(node_id)
    
    async def get_node(self, node_id: str) -> Optional[NodeResponse]:
        """Get a node by ID"""
        # Convert string ID to ObjectId for MongoDB query
        try:
            oid = ObjectId(node_id)
        except Exception:
            # If conversion fails, try as string (for backward compatibility)
            oid = node_id
            
        node = await self.nodes_collection.find_one({"_id": oid})
        
        if not node:
            return None
        
        node["id"] = str(node.pop("_id"))
        return NodeResponse(**node)
    
    async def get_node_with_relations(self, node_id: str) -> Optional[NodeWithRelations]:
        """Get a node with all its relationships"""
        node = await self.get_node(node_id)
        
        if not node:
            return None
        
        # Get outgoing links
        outgoing = await self.links_collection.find({"source": node_id}).to_list(None)
        outgoing_links = []
        for link in outgoing:
            link["id"] = str(link.pop("_id"))
            outgoing_links.append(link)
        
        # Get incoming links
        incoming = await self.links_collection.find({"target": node_id}).to_list(None)
        incoming_links = []
        for link in incoming:
            link["id"] = str(link.pop("_id"))
            incoming_links.append(link)
        
        return NodeWithRelations(
            **node.model_dump(),
            outgoing_links=outgoing_links,
            incoming_links=incoming_links,
        )
    
    async def update_node(self, node_id: str, node_update: NodeUpdate) -> Optional[NodeResponse]:
        """Update a node"""
        # Only update provided fields
        update_data = node_update.model_dump(exclude_unset=True, by_alias=True)
        
        if not update_data:
            return await self.get_node(node_id)
            
        update_data["updated_at"] = datetime.utcnow()
        
        # Convert string ID to ObjectId
        try:
            oid = ObjectId(node_id)
        except Exception:
            oid = node_id
            
        result = await self.nodes_collection.update_one(
            {"_id": oid},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            return None
            
        # Update embedding if content changed
        updated_node_dict = await self.nodes_collection.find_one({"_id": oid})
        if updated_node_dict:
            await self._update_node_embedding(node_id, updated_node_dict)
            
        logger.info(f"✅ Updated node: {node_id}")
        
        return await self.get_node(node_id)
    
    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and its relationships"""
        # Convert string ID to ObjectId
        try:
            oid = ObjectId(node_id)
        except Exception:
            oid = node_id
            
        # Delete from MongoDB
        result = await self.nodes_collection.delete_one({"_id": oid})
        
        if result.deleted_count == 0:
            return False
        
        # Delete all links involving this node
        await self.links_collection.delete_many({
            "$or": [
                {"source": node_id},
                {"target": node_id},
            ]
        })
        
        # Delete from vector database
        try:
            await self.vector_db.delete_node(node_id)
        except Exception as e:
            logger.warning(f"Failed to delete vector for node {node_id}: {e}")

        # Remove node references from all books to keep notebook consistent
        try:
            await self.db.books.update_many(
                {"node_ids": node_id},
                {
                    "$pull": {"node_ids": node_id},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

            books_with_refs = await self.db.books.find(
                {
                    "$or": [
                        {"node_refs.node_id": node_id},
                        {"highlights.node_id": node_id},
                        {"intersections.shared_node_ids": node_id},
                    ]
                }
            ).to_list(length=500)

            for book in books_with_refs:
                node_refs = [r for r in (book.get("node_refs") or []) if r.get("node_id") != node_id]
                highlights = [h for h in (book.get("highlights") or []) if h.get("node_id") != node_id]

                intersections = []
                for i in (book.get("intersections") or []):
                    shared = [sid for sid in (i.get("shared_node_ids") or []) if sid != node_id]
                    if not shared:
                        continue
                    intersections.append(
                        {
                            **i,
                            "shared_node_ids": shared,
                            "shared_count": len(shared),
                        }
                    )

                await self.db.books.update_one(
                    {"_id": book["_id"]},
                    {
                        "$set": {
                            "node_refs": node_refs,
                            "highlights": highlights,
                            "intersections": intersections,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to cleanup books after node delete {node_id}: {e}")
        
        logger.info(f"✅ Deleted node: {node_id}")
        return True
    
    async def get_all_nodes(self, skip: int = 0, limit: int = 100) -> List[NodeResponse]:
        """Get all nodes with pagination"""
        cursor = self.nodes_collection.find().skip(skip).limit(limit)
        nodes = await cursor.to_list(None)
        
        return [
            NodeResponse(id=str(node.pop("_id")), **node)
            for node in nodes
        ]
    
    async def search_nodes(self, query: str, limit: int = 10) -> List[NodeResponse]:
        """Search nodes using vector similarity (semantic search)"""
        from app.services.embedding_service import get_embedding_service
        from app.db.vector_db import vector_db
        
        try:
            # Generate query embedding
            embedding_service = get_embedding_service()
            query_embedding = await embedding_service.encode(query)
            
            # Vector search with lower threshold for broader results
            results = await vector_db.search_similar(
                query_embedding=query_embedding,
                top_k=limit,
                score_threshold=0.2,  # Lower threshold for search (more results)
            )
            
            if not results:
                # Fallback: MongoDB text search
                cursor = self.nodes_collection.find(
                    {"$text": {"$search": query}}
                ).limit(limit)
                
                nodes = await cursor.to_list(None)
                
                return [
                    NodeResponse(id=str(node.pop("_id")), **node)
                    for node in nodes
                ]
            
            # Convert vector results to NodeResponse
            node_responses = []
            for result in results:
                # Fetch full node data from MongoDB
                node_id = result["id"]
                node = await self.nodes_collection.find_one({"_id": ObjectId(node_id)})
                if node:
                    node_responses.append(
                        NodeResponse(
                            id=str(node.pop("_id")),
                            **node,
                            _score=result.get("score", 0)  # Include similarity score
                        )
                    )
            
            return node_responses
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}, falling back to text search")
            
            # Fallback: MongoDB text search
            cursor = self.nodes_collection.find(
                {"$text": {"$search": query}}
            ).limit(limit)
            
            nodes = await cursor.to_list(None)
            
            return [
                NodeResponse(id=str(node.pop("_id")), **node)
                for node in nodes
            ]
    
    # ==================== LINK OPERATIONS ====================
    
    async def create_link(self, link_data: LinkCreate) -> LinkResponse:
        """Create a new link"""
        # Check if nodes exist (convert to ObjectId)
        try:
            source_oid = ObjectId(link_data.source)
            target_oid = ObjectId(link_data.target)
        except Exception:
            source_oid = link_data.source
            target_oid = link_data.target
        
        source_exists = await self.nodes_collection.count_documents({"_id": source_oid})
        target_exists = await self.nodes_collection.count_documents({"_id": target_oid})
        
        if not source_exists or not target_exists:
            raise ValueError("Source or target node does not exist")
        
        # ✅ Check for duplicate links (bidirectional)
        existing_link = await self.links_collection.find_one({
            "$or": [
                {"source": link_data.source, "target": link_data.target},
                {"source": link_data.target, "target": link_data.source}
            ]
        })
        
        if existing_link:
            # Link already exists: strengthen synaptic weight (human-like memory reinforcement)
            now = datetime.utcnow()
            existing_meta = existing_link.get("metadata") or {}
            new_weight = float(existing_meta.get("synaptic_weight", 1.0)) + 0.2

            await self.links_collection.update_one(
                {"_id": existing_link["_id"]},
                {
                    "$set": {
                        "updated_at": now,
                        "metadata.synaptic_weight": round(new_weight, 3),
                        "metadata.last_activated_at": now,
                    },
                    "$inc": {"metadata.activation_count": 1},
                },
            )

            existing_link["updated_at"] = now
            existing_link.setdefault("metadata", {})
            existing_link["metadata"]["synaptic_weight"] = round(new_weight, 3)
            existing_link["metadata"]["activation_count"] = int(existing_meta.get("activation_count", 0)) + 1

            logger.info(f"⏭️ Link already exists: {link_data.source} ⟷ {link_data.target}")
            existing_link["id"] = str(existing_link.pop("_id"))
            return LinkResponse(**existing_link)
        
        # Prepare link document
        link_dict = link_data.model_dump(by_alias=True)
        now = datetime.utcnow()
        link_dict["created_at"] = now
        link_dict["updated_at"] = now
        link_dict.setdefault("metadata", {})
        link_dict["metadata"].setdefault("synaptic_weight", 1.0)
        link_dict["metadata"].setdefault("activation_count", 1)
        link_dict["metadata"]["last_activated_at"] = now
        
        # Insert into MongoDB
        try:
            result = await self.links_collection.insert_one(link_dict)
            link_id = str(result.inserted_id)
            
            logger.info(f"✅ Created link: {link_id} ({link_data.source} -> {link_data.target})")
            
            # Fetch and return the created link
            return await self.get_link(link_id)
        except Exception as e:
            # Handle duplicate link error
            if "duplicate key" in str(e).lower():
                raise ValueError(f"Link already exists between {link_data.source} and {link_data.target}")
            raise
    
    async def get_link(self, link_id: str) -> Optional[LinkResponse]:
        """Get a link by ID"""
        try:
            oid = ObjectId(link_id)
        except Exception:
            oid = link_id
            
        link = await self.links_collection.find_one({"_id": oid})
        
        if not link:
            return None
        
        link["id"] = str(link.pop("_id"))
        return LinkResponse(**link)
    
    async def update_link(self, link_id: str, link_update: LinkUpdate) -> Optional[LinkResponse]:
        """Update a link"""
        update_data = link_update.model_dump(exclude_unset=True, by_alias=True)
        
        if not update_data:
            return await self.get_link(link_id)
        
        update_data["updated_at"] = datetime.utcnow()
        
        try:
            oid = ObjectId(link_id)
        except Exception:
            oid = link_id
            
        result = await self.links_collection.update_one(
            {"_id": oid},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            return None
        
        logger.info(f"✅ Updated link: {link_id}")
        
        return await self.get_link(link_id)
    
    async def delete_link(self, link_id: str) -> bool:
        """Delete a link"""
        try:
            oid = ObjectId(link_id)
        except Exception:
            oid = link_id
            
        result = await self.links_collection.delete_one({"_id": oid})
        
        if result.deleted_count == 0:
            return False
        
        logger.info(f"✅ Deleted link: {link_id}")
        return True
    
    async def get_all_links(self, skip: int = 0, limit: int = 1000) -> List[LinkResponse]:
        """Get all links with pagination"""
        cursor = self.links_collection.find().skip(skip).limit(limit)
        links = await cursor.to_list(None)
        
        return [
            LinkResponse(id=str(link.pop("_id")), **link)
            for link in links
        ]
    
    async def get_node_links(self, node_id: str) -> Dict[str, List[LinkResponse]]:
        """Get all links for a specific node"""
        # Outgoing links
        outgoing_cursor = self.links_collection.find({"source": node_id})
        outgoing = await outgoing_cursor.to_list(None)
        
        # Incoming links
        incoming_cursor = self.links_collection.find({"target": node_id})
        incoming = await incoming_cursor.to_list(None)
        
        return {
            "outgoing": [LinkResponse(id=str(link.pop("_id")), **link) for link in outgoing],
            "incoming": [LinkResponse(id=str(link.pop("_id")), **link) for link in incoming],
        }
    
    # ==================== GRAPH OPERATIONS ====================
    
    async def get_full_graph(self) -> GraphData:
        """Get the entire graph"""
        nodes = await self.get_all_nodes(limit=10000)
        links = await self.get_all_links(limit=10000)
        
        return GraphData(nodes=nodes, links=links)
    
    async def bulk_create_nodes(self, nodes: List[NodeCreate]) -> List[NodeResponse]:
        """Create multiple nodes at once"""
        created_nodes = []
        
        for node_data in nodes:
            try:
                node = await self.create_node(node_data)
                created_nodes.append(node)
            except Exception as e:
                logger.error(f"Failed to create node {node_data.label}: {e}")
        
        return created_nodes
    
    async def bulk_create_links(self, links: List[LinkCreate]) -> List[LinkResponse]:
        """Create multiple links at once"""
        created_links = []
        
        for link_data in links:
            try:
                link = await self.create_link(link_data)
                created_links.append(link)
            except Exception as e:
                logger.error(f"Failed to create link {link_data.source} -> {link_data.target}: {e}")
        
        return created_links
    
    async def batch_create_with_dedup(
        self,
        nodes: List[Dict[str, Any]],
        links: List[Dict[str, Any]],
        book_data: Optional[Dict[str, Any]] = None,
        persist_book_memory: bool = True,
    ) -> Dict[str, Any]:
        """
        🚀 OPTIMIZED: Batch create nodes + links with entity matching
        
        Performance improvements:
        - Batch embedding generation (19 nodes: 10s → 1s)
        - Batch vector search (19 queries: 10s → 2s)
        - Bulk MongoDB insert (19 inserts: 4s → 0.5s)
        - Bulk Qdrant insert (19 inserts: 6s → 0.5s)
        
        Total: ~30s → ~5s (6x faster!)
        """
        import time
        start_time = time.time()
        
        created_nodes = []
        label_to_id = {}  # Map label → node_id
        
        stats = {
            "new_nodes": 0,
            "merged_nodes": 0,
            "new_links": 0,
            "skipped_links": 0
        }
        
        logger.info(f"📦 Batch create: {len(nodes)} nodes, {len(links)} links")
        
        # ===== Phase 1: BATCH Embedding Generation =====
        phase1_start = time.time()
        logger.info("🧠 Phase 1: Generating embeddings in batch...")
        
        texts_for_embedding = []
        for node_data in nodes:
            label = node_data.get("label", "")
            content = node_data.get("content", "")
            text = f"{label}. {content}".strip()
            texts_for_embedding.append(text)
        
        # Generate ALL embeddings in ONE model call (true batch — much faster than a loop)
        embedding_service = get_embedding_service()
        if texts_for_embedding:
            all_embeddings = await embedding_service.encode(texts_for_embedding)
            # encode() returns List[List[float]] when given a list; guard for edge cases
            if all_embeddings and not isinstance(all_embeddings[0], list):
                all_embeddings = [all_embeddings]
        else:
            all_embeddings = []

        logger.info(f"✅ Generated {len(all_embeddings)} embeddings in {time.time() - phase1_start:.2f}s")
        
        # ===== Phase 2: BATCH Vector Search for Deduplication (with label fallback) =====
        phase2_start = time.time()
        logger.info("🔍 Phase 2: Batch vector search + label fallback for entity matching...")

        matched_nodes = []  # Store matched existing nodes
        for i, embedding in enumerate(all_embeddings):
            label = nodes[i].get("label", "").strip()

            # --- Try vector similarity first ---
            results = await vector_db.search_similar(
                query_embedding=embedding,
                top_k=1,
                score_threshold=0.75,
            )

            if results:
                matched_nodes.append((i, results[0]))
                continue

            # --- Vector search empty: fallback to case-insensitive label match ---
            if label:
                existing = await self.nodes_collection.find_one(
                    {"label": {"$regex": f"^{re.escape(label)}$", "$options": "i"}}
                )
                if existing:
                    logger.info(f"🔤 Label-match fallback: '{label}' → '{existing['label']}'")
                    matched_nodes.append(
                        (
                            i,
                            {
                                "id": str(existing["_id"]),
                                "score": 1.0,
                                "payload": {
                                    "label": existing["label"],
                                    "type": existing.get("type", "Concept"),
                                    "content": existing.get("content", ""),
                                },
                            },
                        )
                    )
                    continue

            matched_nodes.append((i, None))

        logger.info(f"✅ Completed {len(matched_nodes)} searches in {time.time() - phase2_start:.2f}s")
        
        # ===== Phase 3: BULK Node Creation =====
        phase3_start = time.time()
        logger.info("⚡ Phase 3: Bulk node creation...")
        
        new_nodes_to_create = []
        new_nodes_indices = []
        
        for i, (idx, match) in enumerate(matched_nodes):
            node_data = nodes[idx]
            label = node_data.get("label", "")
            
            if match:
                # Reuse existing node
                existing_node_id = match["id"]
                existing_node = await self.get_node(existing_node_id)
                
                if existing_node:
                    logger.info(f"♻️ Reusing: '{label}' → '{existing_node.label}'")

                    # Human-like memory consolidation:
                    # if incoming content has new details, append to the existing node
                    incoming_content = (node_data.get("content") or "").strip()
                    existing_content = (existing_node.content or "").strip()
                    if incoming_content and incoming_content not in existing_content:
                        merged_content = (
                            f"{existing_content}\n\n[เพิ่มเติมจากเอกสารใหม่]\n{incoming_content}"
                            if existing_content
                            else incoming_content
                        )
                        await self.update_node(
                            existing_node.id,
                            NodeUpdate(content=merged_content)
                        )
                        # Refresh node snapshot after update
                        existing_node = await self.get_node(existing_node.id)

                    created_nodes.append(existing_node)
                    label_to_id[label] = existing_node.id
                    stats["merged_nodes"] += 1
                else:
                    # Node deleted, create new
                    new_nodes_to_create.append((idx, node_data, all_embeddings[idx]))
                    new_nodes_indices.append(len(created_nodes))
                    created_nodes.append(None)  # Placeholder
            else:
                # New node
                new_nodes_to_create.append((idx, node_data, all_embeddings[idx]))
                new_nodes_indices.append(len(created_nodes))
                created_nodes.append(None)  # Placeholder
        
        # BULK INSERT to MongoDB
        if new_nodes_to_create:
            from datetime import datetime
            
            # Prepare MongoDB documents (WITH EMBEDDINGS for Atlas Vector Search)
            mongo_docs = []
            for idx, node_data, embedding in new_nodes_to_create:
                # Convert numpy array to list if needed
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()
                
                doc = {
                    "_id": ObjectId(),
                    "label": node_data.get("label", ""),
                    "type": node_data.get("type", "Concept"),
                    "content": node_data.get("content", ""),
                    "embedding": embedding,  # ✅ Store embedding in MongoDB for Atlas Vector Search
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                mongo_docs.append(doc)
            
            # Bulk insert to MongoDB (with embeddings)
            result = await self.nodes_collection.insert_many(mongo_docs)
            logger.info(f"✅ MongoDB: Inserted {len(result.inserted_ids)} nodes with embeddings")
            
            # Update created_nodes with actual NodeResponse objects
            for i, (idx, node_data, _) in enumerate(new_nodes_to_create):
                mongo_doc = mongo_docs[i]
                node_response = NodeResponse(
                    id=str(mongo_doc["_id"]),
                    label=mongo_doc["label"],
                    type=mongo_doc["type"],
                    content=mongo_doc["content"],
                    created_at=mongo_doc["created_at"],
                    updated_at=mongo_doc["updated_at"]
                )
                
                # Fill placeholder
                placeholder_idx = new_nodes_indices[i]
                created_nodes[placeholder_idx] = node_response
                label_to_id[node_data.get("label", "")] = node_response.id
                stats["new_nodes"] += 1
        
        logger.info(f"✅ Created {stats['new_nodes']} new nodes in {time.time() - phase3_start:.2f}s")
        
        # ===== Phase 4: BULK Link Creation with Deduplication =====
        # Build a label→id lookup that also covers existing nodes (for cross-book links).
        phase4_start = time.time()
        logger.info("🔗 Phase 4: Bulk link creation (with existing-node label resolution)...")

        created_links = []

        # Resolve a label to a node ID: batch map first → DB exact → DB case-insensitive
        async def resolve_label(lbl: str) -> Optional[str]:
            if not lbl:
                return None
            # Already in the batch
            if lbl in label_to_id:
                return label_to_id[lbl]
            # Exact match in DB (O(log n) with index)
            existing = await self.nodes_collection.find_one({"label": lbl}, {"_id": 1})
            if existing:
                nid = str(existing["_id"])
                label_to_id[lbl] = nid          # cache for later links
                return nid
            # Case-insensitive match
            existing = await self.nodes_collection.find_one(
                {"label": {"$regex": f"^{re.escape(lbl)}$", "$options": "i"}}, {"_id": 1, "label": 1}
            )
            if existing:
                nid = str(existing["_id"])
                label_to_id[lbl] = nid          # cache under original label too
                label_to_id[existing["label"]] = nid
                return nid
            return None

        for link_data in links:
            source_label = link_data.get("source_label") or link_data.get("source")
            target_label = link_data.get("target_label") or link_data.get("target")

            source_id = await resolve_label(source_label)
            target_id = await resolve_label(target_label)

            # Skip if nodes not found or self-loop
            if not source_id or not target_id or source_id == target_id:
                stats["skipped_links"] += 1
                continue
            
            # Create link (create_link already checks for duplicates)
            try:
                link = await self.create_link(LinkCreate(
                    source=source_id,
                    target=target_id,
                    label=link_data.get("label", "เกี่ยวข้องกับ"),
                    labelReverse=link_data.get("labelReverse") or link_data.get("label_reverse", "เกี่ยวข้องกับ")
                ))
                
                # Check if it's a new link or existing
                if link.created_at == link.updated_at:
                    stats["new_links"] += 1
                else:
                    stats["skipped_links"] += 1
                    
                created_links.append(link)
            except ValueError as e:
                # Duplicate link
                logger.debug(f"⏭️ Link exists: {source_label} → {target_label}")
                stats["skipped_links"] += 1
            except Exception as e:
                logger.error(f"Failed to create link {source_label} → {target_label}: {e}")
                stats["skipped_links"] += 1
        
        logger.info(f"✅ Created {stats['new_links']} links in {time.time() - phase4_start:.2f}s")
        
        # ===== Final Stats =====
        total_time = time.time() - start_time
        logger.info(
            f"🎉 Batch complete in {total_time:.2f}s: "
            f"{stats['new_nodes']} new nodes, "
            f"{stats['merged_nodes']} merged, "
            f"{stats['new_links']} new links, "
            f"{stats['skipped_links']} skipped"
        )
        
        # ===== Phase 5: Knowledge-based linking to existing graph =====
        if stats["new_nodes"] > 0:
            logger.info("🧠 Phase 5: Knowledge-based linking to existing graph...")
            valid_created = [n for n in created_nodes if n is not None]
            auto_links = await self._knowledge_link_new_nodes(valid_created)
            created_links.extend(auto_links)
            stats["new_links"] += len(auto_links)
            logger.info(f"🧠 Knowledge links: +{len(auto_links)} links")

            # Fallback when knowledge inference produced few/no links.
            if len(auto_links) == 0:
                logger.info("🔗 Knowledge links are empty, applying similarity fallback...")
                fallback_links = await self._auto_link_isolated_nodes(valid_created, label_to_id)
                created_links.extend(fallback_links)
                stats["new_links"] += len(fallback_links)
                logger.info(f"🔗 Similarity fallback links: +{len(fallback_links)} links")

        # ===== Phase 6: Persist book memory (full text + highlighted nodes) =====
        if persist_book_memory and book_data and (book_data.get("full_text") or "").strip():
            try:
                await self._upsert_book_memory(
                    book_data=book_data,
                    created_nodes=[n for n in created_nodes if n is not None],
                    stats=stats,
                )
            except Exception as e:
                logger.warning(f"Book memory save failed: {e}")
        
        return {
            "nodes": created_nodes,
            "links": created_links,
            "stats": stats
        }

    async def _upsert_book_memory(
        self,
        book_data: Dict[str, Any],
        created_nodes: List[NodeResponse],
        stats: Dict[str, int],
    ) -> None:
        """
        Store uploaded/parsed content as a "book" and bind node references.
        Also computes intersections with existing books based on shared nodes.
        """
        full_text = (book_data.get("full_text") or "").strip()
        if not full_text:
            return

        title = (book_data.get("title") or "Untitled Book").strip()
        source_type = (book_data.get("source_type") or "text").strip()
        now = datetime.utcnow()

        node_refs = []
        node_ids = []
        highlights = []

        for node in created_nodes:
            if not node:
                continue
            label = (node.label or "").strip()
            if not label:
                continue

            node_ids.append(node.id)

            # Find up to 5 highlight positions for the label in the full text
            for m in re.finditer(re.escape(label), full_text, flags=re.IGNORECASE):
                highlights.append(
                    {
                        "node_id": node.id,
                        "label": label,
                        "start": m.start(),
                        "end": m.end(),
                    }
                )
                if len([h for h in highlights if h["node_id"] == node.id]) >= 5:
                    break

            node_refs.append(
                {
                    "node_id": node.id,
                    "label": label,
                    "type": node.type,
                }
            )

        # Compute intersections with existing books (shared nodes)
        intersections = []
        if node_ids:
            cursor = self.db.books.find({"node_ids": {"$in": node_ids}})
            existing_books = await cursor.to_list(length=200)
            for b in existing_books:
                other_ids = set(b.get("node_ids", []))
                shared = list(set(node_ids).intersection(other_ids))
                if not shared:
                    continue
                intersections.append(
                    {
                        "book_id": str(b.get("_id")),
                        "title": b.get("title", "Untitled Book"),
                        "shared_node_ids": shared,
                        "shared_count": len(shared),
                    }
                )

        doc = {
            "title": title,
            "source_type": source_type,
            "filename": book_data.get("filename"),
            "full_text": full_text,
            "node_ids": list(dict.fromkeys(node_ids)),
            "node_refs": node_refs,
            "highlights": highlights,
            "intersections": intersections,
            "stats": stats,
            "created_at": now,
            "updated_at": now,
        }

        # Insert as a new book snapshot (append-only memory style)
        await self.db.books.insert_one(doc)
    
    # ==================== PRIVATE METHODS ====================
    
    async def suggest_connections(
        self,
        node_id: str,
        top_k: int = 5,
        threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Find existing nodes semantically similar to a given node.
        Used to suggest connections right after manual node creation.
        """
        node = await self.get_node(node_id)
        if not node:
            return []

        text = f"{node.label}. {node.content or ''}"
        try:
            query_embedding = await self.embedding_service.encode(text)
            results = await self.vector_db.search_similar(
                query_embedding=query_embedding,
                top_k=top_k + 1,  # +1 because the node itself may appear
                score_threshold=threshold,
            )
        except Exception as e:
            logger.warning(f"suggest_connections vector search failed: {e}")
            return []

        raw_suggestions = [
            {
                "id": r["id"],
                "label": r["payload"]["label"],
                "type": r["payload"].get("type", "Concept"),
                "content": r["payload"].get("content", ""),
                "similarity": round(r["score"], 3),
            }
            for r in results
            if r["id"] != node_id
        ]

        suggestions = raw_suggestions[:top_k]
        if not suggestions:
            return []

        # Infer better relationship labels using knowledge (not only similarity)
        try:
            pairs = [
                {
                    "source_id": node.id,
                    "source_label": node.label,
                    "source_type": node.type,
                    "source_content": (node.content or "")[:220],
                    "target_id": s["id"],
                    "target_label": s["label"],
                    "target_type": s.get("type", "Concept"),
                    "target_content": (s.get("content") or "")[:220],
                    "similarity": s.get("similarity", 0.0),
                }
                for s in suggestions
            ]

            inferred = await self.gemini_service.infer_relationships(pairs, max_links=top_k)
            inferred_map = {
                (x.get("source_id"), x.get("target_id")): x
                for x in inferred
                if isinstance(x, dict)
            }

            enhanced = []
            for s in suggestions:
                k = (node.id, s["id"])
                info = inferred_map.get(k, {})
                enhanced.append(
                    {
                        **s,
                        "suggested_label": info.get("label", "เกี่ยวข้องกับ"),
                        "suggested_label_reverse": info.get("labelReverse", "เกี่ยวข้องกับ"),
                        "inference_confidence": round(float(info.get("confidence", 0.0)), 3),
                        "inference_reason": info.get("reason", ""),
                    }
                )

            enhanced.sort(
                key=lambda x: (
                    float(x.get("inference_confidence", 0.0)),
                    float(x.get("similarity", 0.0)),
                ),
                reverse=True,
            )
            return enhanced[:top_k]
        except Exception as e:
            logger.warning(f"suggest_connections inference failed: {e}")
            return suggestions

    async def _auto_link_isolated_nodes(
        self,
        nodes: List[NodeResponse],
        label_to_id: Dict[str, str]
    ) -> List[LinkResponse]:
        """
        Auto-link nodes to similar EXISTING graph nodes using vector similarity.
        Only creates links to nodes outside the current batch to avoid duplicating
        what Phase 4 already handled.

        Args:
            nodes: List of newly created nodes
            label_to_id: Mapping of label → node ID for nodes in this batch

        Returns:
            List of auto-created links
        """
        auto_links = []
        # IDs of nodes created in this batch — don't cross-link within batch here
        batch_ids = {n.id for n in nodes if n is not None}

        try:
            # Get existing link counts only to skip already well-connected nodes
            node_ids = [n.id for n in nodes]
            existing_link_count = {}

            for node_id in node_ids:
                count = await self.links_collection.count_documents({
                    "$or": [{"source": node_id}, {"target": node_id}]
                })
                existing_link_count[node_id] = count
            
            # Try to connect all new nodes (isolated ones first, but also lightly-connected)
            isolated_nodes = [n for n in nodes if existing_link_count.get(n.id, 0) <= 1]

            if not isolated_nodes:
                return auto_links

            logger.info(f"🔍 Attempting cross-graph links for {len(isolated_nodes)} nodes...")
            
            # For each isolated node, find similar neighbors
            for node in isolated_nodes:
                try:
                    # Generate embedding
                    text = f"{node.label}. {node.content or ''}"
                    query_embedding = await self.embedding_service.encode(text)
                    
                    # Search for similar nodes (higher threshold = more relevant)
                    results = await self.vector_db.search_similar(
                        query_embedding=query_embedding,
                        top_k=5,
                        score_threshold=0.7  # 70% similarity (relaxed for auto-linking)
                    )
                    
                    # Link to top similar nodes that are NOT in this batch
                    for result in results[:3]:
                        neighbor_id = result["id"]
                        similarity = result["score"]
                        neighbor_label = result["payload"]["label"]

                        # Skip self-link and nodes from the same batch (Phase 4 handled those)
                        if neighbor_id == node.id or neighbor_id in batch_ids:
                            continue
                        
                        # Check if link already exists
                        existing = await self.links_collection.find_one({
                            "$or": [
                                {"source": node.id, "target": neighbor_id},
                                {"source": neighbor_id, "target": node.id}
                            ]
                        })
                        
                        if existing:
                            continue
                        
                        # Create generic link
                        link = await self.create_link(LinkCreate(
                            source=node.id,
                            target=neighbor_id,
                            label="เกี่ยวข้องกับ",
                            labelReverse="เกี่ยวข้องกับ"
                        ))
                        
                        auto_links.append(link)
                        logger.info(
                            f"🔗 Auto-linked: '{node.label}' ⟷ '{neighbor_label}' "
                            f"(similarity: {similarity:.3f})"
                        )
                        
                except Exception as e:
                    logger.error(f"Failed to auto-link node '{node.label}': {e}")
            
        except Exception as e:
            logger.error(f"Smart linking failed: {e}")
        
        return auto_links

    async def _knowledge_link_new_nodes(self, nodes: List[NodeResponse]) -> List[LinkResponse]:
        """
        Use semantic candidates + Gemini inference to create meaningful cross-graph links.
        Falls back to MongoDB-sampled existing nodes when vector search returns nothing.
        """
        if not nodes:
            return []

        auto_links: List[LinkResponse] = []
        batch_ids = {n.id for n in nodes if n is not None}

        candidate_pairs: List[Dict[str, Any]] = []
        seen_pairs = set()

        for node in nodes:
            if not node:
                continue
            try:
                text = f"{node.label}. {node.content or ''}"
                query_embedding = await self.embedding_service.encode(text)
                results = await self.vector_db.search_similar(
                    query_embedding=query_embedding,
                    top_k=8,
                    score_threshold=0.50,   # relaxed from 0.55 so more candidates surface
                )

                for result in results:
                    neighbor_id = result["id"]
                    if neighbor_id == node.id or neighbor_id in batch_ids:
                        continue

                    pair_key = tuple(sorted([node.id, neighbor_id]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    candidate_pairs.append(
                        {
                            "source_id": node.id,
                            "source_label": node.label,
                            "source_type": node.type,
                            "source_content": (node.content or "")[:220],
                            "target_id": neighbor_id,
                            "target_label": result["payload"].get("label", ""),
                            "target_type": result["payload"].get("type", "Concept"),
                            "target_content": (result["payload"].get("content", "") or "")[:220],
                            "similarity": round(float(result.get("score", 0.0)), 4),
                        }
                    )
            except Exception as e:
                logger.warning(f"Knowledge candidate search failed for '{node.label}': {e}")

        # ── Fallback: vector search returned nothing ──────────────────────────────
        # Pull existing nodes directly from MongoDB and pair them with new nodes so
        # that Gemini can reason about relationships without vector search.
        if not candidate_pairs:
            logger.info(
                "⚠️  Vector search returned no candidates — "
                "falling back to MongoDB-sampled existing nodes for Gemini reasoning."
            )
            try:
                # Prefer hub nodes (high link-count) + recent nodes — more likely related.
                batch_oids = [ObjectId(bid) for bid in batch_ids if ObjectId.is_valid(bid)]

                # Recently updated nodes (up to 40)
                recent_cursor = self.nodes_collection.find(
                    {"_id": {"$nin": batch_oids}}
                ).sort("updated_at", -1).limit(40)
                recent_nodes = await recent_cursor.to_list(length=40)

                # Hub nodes by incoming/outgoing link frequency (up to 40)
                hub_pipeline = [
                    {"$group": {"_id": "$source", "cnt": {"$sum": 1}}},
                    {"$sort": {"cnt": -1}},
                    {"$limit": 40},
                ]
                hub_ids_raw = await self.links_collection.aggregate(hub_pipeline).to_list(length=40)
                hub_ids = [
                    ObjectId(h["_id"])
                    for h in hub_ids_raw
                    if h["_id"] and ObjectId.is_valid(h["_id"])
                    and ObjectId(h["_id"]) not in batch_oids
                ]
                hub_nodes = []
                if hub_ids:
                    hub_cursor = self.nodes_collection.find({"_id": {"$in": hub_ids[:40]}})
                    hub_nodes = await hub_cursor.to_list(length=40)

                # Deduplicate keeping hubs first, then recent
                seen_ex = set()
                existing_nodes = []
                for nd in hub_nodes + recent_nodes:
                    nid = str(nd["_id"])
                    if nid not in seen_ex:
                        seen_ex.add(nid)
                        existing_nodes.append(nd)
                existing_nodes = existing_nodes[:60]  # hard cap

                for node in nodes:
                    if not node:
                        continue
                    for ex in existing_nodes:
                        neighbor_id = str(ex["_id"])
                        pair_key = tuple(sorted([node.id, neighbor_id]))
                        if pair_key in seen_pairs:
                            continue
                        seen_pairs.add(pair_key)
                        candidate_pairs.append(
                            {
                                "source_id": node.id,
                                "source_label": node.label,
                                "source_type": node.type,
                                "source_content": (node.content or "")[:220],
                                "target_id": neighbor_id,
                                "target_label": ex.get("label", ""),
                                "target_type": ex.get("type", "Concept"),
                                "target_content": (ex.get("content") or "")[:220],
                                "similarity": 0.0,  # unknown; Gemini decides on knowledge alone
                            }
                        )
            except Exception as e:
                logger.warning(f"MongoDB fallback candidate fetch failed: {e}")

        if not candidate_pairs:
            return []

        # Keep highest-similarity candidates first, then MongoDB-fallback pairs (similarity=0).
        # Ensure we include at least some fallback pairs so Gemini can reason across books.
        vector_pairs = [p for p in candidate_pairs if p["similarity"] > 0.0]
        fallback_pairs = [p for p in candidate_pairs if p["similarity"] == 0.0]
        vector_pairs.sort(key=lambda x: x["similarity"], reverse=True)
        # Cap: take top 40 vector pairs + up to 40 fallback pairs (total ≤ 80 for Gemini)
        candidate_pairs = (vector_pairs[:40] + fallback_pairs[:40])[:80]

        inferred_links: List[Dict[str, Any]] = []
        try:
            inferred_links = await self.gemini_service.infer_relationships(candidate_pairs, max_links=20)
        except Exception as e:
            logger.warning(f"Gemini relationship inference failed: {e}")
            inferred_links = []

        if not inferred_links:
            return []

        # Build a quick map for similarity fallback and source quotas.
        pair_similarity_map = {
            (c["source_id"], c["target_id"]): c["similarity"] for c in candidate_pairs
        }
        links_per_source: Dict[str, int] = {}

        # Prioritize confident links first.
        inferred_links = sorted(
            inferred_links,
            key=lambda x: float(x.get("confidence", 0.0)),
            reverse=True,
        )

        for item in inferred_links:
            source_id = str(item.get("source_id", "")).strip()
            target_id = str(item.get("target_id", "")).strip()
            if not source_id or not target_id or source_id == target_id:
                continue

            confidence = float(item.get("confidence", 0.0))
            similarity = pair_similarity_map.get((source_id, target_id), 0.0)

            # For MongoDB-fallback pairs (similarity=0) accept if Gemini ≥ 0.60;
            # for vector pairs require either high confidence or good similarity.
            if similarity == 0.0:
                if confidence < 0.60:
                    continue
            else:
                if confidence < 0.55 and similarity < 0.75:
                    continue

            # Allow up to 3 links per source node (raised from 2 to capture cross-book links).
            if links_per_source.get(source_id, 0) >= 3:
                continue

            label = str(item.get("label", "เกี่ยวข้องกับ")).strip() or "เกี่ยวข้องกับ"
            label_reverse = str(item.get("labelReverse", "เกี่ยวข้องกับ")).strip() or "เกี่ยวข้องกับ"

            # Double-check duplication before insert.
            existing = await self.links_collection.find_one(
                {
                    "$or": [
                        {"source": source_id, "target": target_id},
                        {"source": target_id, "target": source_id},
                    ]
                }
            )
            if existing:
                continue

            try:
                link = await self.create_link(
                    LinkCreate(
                        source=source_id,
                        target=target_id,
                        label=label,
                        labelReverse=label_reverse,
                        metadata={
                            "link_strategy": "knowledge_inference",
                            "inference_confidence": round(confidence, 3),
                            "semantic_similarity": round(similarity, 3),
                            "inference_reason": str(item.get("reason", ""))[:240],
                        },
                    )
                )
                auto_links.append(link)
                links_per_source[source_id] = links_per_source.get(source_id, 0) + 1
            except Exception as e:
                logger.warning(
                    f"Failed to create inferred link {source_id} -> {target_id}: {e}"
                )

        return auto_links
    
    async def _update_node_embedding(self, node_id: str, node_dict: Dict[str, Any]):
        """
        Generate and store embedding for a node
        
        NOTE: With MongoDB Atlas Vector Search, embeddings are stored 
        directly in the nodes collection, not in a separate vector database
        """
        try:
            # Generate embedding
            text = f"{node_dict['label']}. {node_dict.get('content', '')}"
            embedding = await self.embedding_service.encode(text)
            
            # Convert to list if numpy array
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
            
            # Store embedding in MongoDB (both vector_db and nodes collection)
            await self.vector_db.upsert_node(
                node_id=node_id,
                embedding=embedding,
                payload={
                    "label": node_dict["label"],
                    "type": node_dict.get("type", "Concept"),
                    "content": node_dict.get("content", ""),
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to update embedding for node {node_id}: {e}")


def get_graph_service(db: AsyncIOMotorDatabase) -> GraphService:
    """Factory function to create GraphService instance"""
    return GraphService(db)
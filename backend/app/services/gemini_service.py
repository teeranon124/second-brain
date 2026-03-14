"""Gemini AI Service"""

import google.generativeai as genai
from typing import Optional, Dict, Any, List
import logging
import asyncio
import json
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Google Gemini API"""
    
    def __init__(self):
        self.model = None
        self._initialized = False
    
    def initialize(self):
        """Initialize Gemini API"""
        if self._initialized:
            return
        
        settings = get_settings()
        
        if not settings.gemini_api_key:
            logger.warning("⚠️ Gemini API key not configured")
            return
        
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        self._initialized = True
        
        logger.info(f"✅ Gemini API initialized: {settings.gemini_model}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate content using Gemini API
        
        Args:
            prompt: User prompt
            system_instruction: System instruction for the model
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            Generated text response
        """
        self.initialize()
        
        if not self._initialized:
            raise RuntimeError("Gemini API not initialized")
        
        # Run API call in thread pool
        loop = asyncio.get_event_loop()
        
        try:
            # Combine system instruction with prompt if provided
            full_prompt = prompt
            if system_instruction:
                full_prompt = f"{system_instruction}\n\n{prompt}"
            
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                    ),
                ),
            )
            
            return response.text
        
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
    
    async def extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract entities and relationships from text using Gemini
        
        Args:
            text: Input text to extract from
            
        Returns:
            Dictionary with 'nodes' and 'links' keys
        """
        system_instruction = """คุณคือ Data Extractor สำหรับระบบ GraphRAG - สกัดความรู้เป็น nodes และ links

**Output Format (JSON only):**
{"nodes": [{"label": "ชื่อสั้น", "type": "ประเภท", "content": "อธิบายสั้นๆ"}], "links": [{"source": "label_โหนดต้นทาง", "target": "label_โหนดปลายทาง", "label": "ความสัมพันธ์", "labelReverse": "ความสัมพันธ์ย้อนกลับ"}]}

**Node Types:** Company, Person, Organization, Concept, Product, Event, Location, Technology

**CRITICAL: แยก Nodes vs Links อย่างชัดเจน**

**NODES (โหนด) = หัวข้อหลัก/สิ่งที่จับต้องได้:**
- ✅ บุคคล: "Elon Musk", "Steve Jobs"
- ✅ องค์กร: "Tesla", "Apple", "OpenAI"
- ✅ แนวคิด: "Artificial Intelligence", "Blockchain"
- ✅ สถานที่: "Silicon Valley", "Thailand"
- ✅ ผลิตภัณฑ์: "iPhone", "ChatGPT"
- ❌ ไม่ใช่: คำกริยา "เป็นผู้นำ", "พัฒนา", "ลงทุน" <- เหล่านี้ต้องเป็น LINK label

**LINKS (ลิงก์) = ความสัมพันธ์/การกระทำ:**
- label ใช้คำกริยา/ความสัมพันธ์: "เป็นผู้นำ", "พัฒนา", "ลงทุนใน", "ทำงานที่"
- labelReverse: ความสัมพันธ์ย้อนกลับ
- สร้างครบทุกความสัมพันธ์ที่พบ

**ตัวอย่างที่ถูก:**
ข้อความ: "Elon Musk เป็นผู้ก่อตั้ง Tesla และ SpaceX"
- Nodes: [{"label":"Elon Musk","type":"Person"}, {"label":"Tesla","type":"Company"}, {"label":"SpaceX","type":"Company"}]
- Links: [{"source":"Elon Musk","target":"Tesla","label":"ก่อตั้ง","labelReverse":"ถูกก่อตั้งโดย"}, {"source":"Elon Musk","target":"SpaceX","label":"ก่อตั้ง","labelReverse":"ถูกก่อตั้งโดย"}]

**ตัวอย่างที่ผิด (อย่าทำ):**
- ❌ Node: {"label":"ก่อตั้ง"} <- นี่ควรเป็น link label ไม่ใช่ node
- ❌ Node: {"label":"เป็นผู้นำใน"} <- นี่คือความสัมพันธ์ ไม่ใช่สิ่ง
"""
        
        prompt = f"สกัดความรู้จากข้อความนี้:\n\n{text}"
        
        response_text = await self.generate_content(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.3,  # Lower temperature for more consistent extraction
        )
        
        # Parse JSON response
        extracted_data = self._safe_json_parse(response_text)
        
        if not extracted_data:
            logger.warning("❌ Failed to parse extraction result")
            return {"nodes": [], "links": []}
        
        # Log extraction stats
        num_nodes = len(extracted_data.get("nodes", []))
        num_links = len(extracted_data.get("links", []))
        logger.info(f"📦 Extracted: {num_nodes} nodes, {num_links} links")
        
        # Log node labels for debugging
        if num_nodes > 0:
            node_labels = [n.get("label", "Unknown") for n in extracted_data.get("nodes", [])[:10]]
            logger.info(f"📋 Nodes: {', '.join(node_labels)}{' ...' if num_nodes > 10 else ''}")
        
        # Warn if no links extracted
        if num_nodes > 1 and num_links == 0:
            logger.warning(f"⚠️ Warning: {num_nodes} nodes but NO links extracted!")
        
        return extracted_data
    
    async def dense_retrieval(
        self,
        query: str,
        nodes: list[Dict[str, Any]],
        top_k: int = 2,
    ) -> list[str]:
        """
        Use Gemini for semantic matching (as fallback to vector search)
        
        Args:
            query: Search query
            nodes: List of node dictionaries
            top_k: Number of top results to return
            
        Returns:
            List of node IDs
        """
        node_list = [{"id": n["id"], "label": n["label"]} for n in nodes]
        
        prompt = f"""ข้อมูลโหนด: {json.dumps(node_list, ensure_ascii=False)}

คำถาม: "{query}"

**คำแนะนำสำคัญ:**
1. ค้นหาโหนดที่มีความหมาย**เกี่ยวข้องโดยตรง**กับคำถาม (สูงสุด {top_k} อันดับ)
2. **พิจารณาคำที่คล้ายกัน:** คำที่เขียนผิด, คำพ้อง, คำที่มีความหมายเดียวกัน
3. **พิจารณาบริบท:** ถ้าคำถามมีหลายคำ ให้ดูว่าโหนดใดตรงกับบริบทมากที่สุด
4. **พิจารณาคำแปล/ชื่อภาษาอื่น:** 
   - "เอนวิเดีย"/"Nvidia" -> "NVDA" (ticker symbol)
   - "เทสลา" -> "Tesla"
   - "หุ้น Nvidia" -> "NVDA"
   - คำถามภาษาไทยอาจหมายถึงโหนดภาษาอังกฤษหรือย่อตัว
5. ถ้า**ไม่มีโหนดใดเกี่ยวข้อง** ให้ตอบ: []
6. อย่าเลือกโหนดที่ไม่เกี่ยวข้อง

**ตัวอย่าง:**
- คำถาม "ทีมบนบก" -> เจอโหนด "หินบนบก" (คำคล้ายกัน + บริบท "บนบก" ตรง)
- คำถาม "พชยุน" -> เจอโหนด "พชยูน" (เขียนผิด)
- คำถาม "สุนัข" -> เจอโหนด "น้องหมา" (คำพ้อง)
- คำถาม "เอนวิเดีย คืออะไร" -> เจอโหนด "NVDA" (ชื่อภาษาไทย -> ticker symbol)

ตอบเป็น JSON Array ของ ID เท่านั้น: ["id1", "id2"] หรือ []"""
        
        response_text = await self.generate_content(
            prompt=prompt,
            temperature=0.1,
        )
        
        # Parse JSON response
        node_ids = self._safe_json_parse(response_text)
        
        if isinstance(node_ids, list):
            return node_ids[:top_k]
        
        return []
    
    async def generate_answer(
        self,
        query: str,
        context: str,
        sources: list[str],
    ) -> str:
        """
        Generate answer from retrieved context
        
        Args:
            query: User's original query
            context: Retrieved context from graph
            sources: Source node labels
            
        Returns:
            Generated answer
        """
        # Truncate context if too long (save tokens)
        MAX_CONTEXT_LENGTH = 3000  # ~750 tokens
        if len(context) > MAX_CONTEXT_LENGTH:
            context = context[:MAX_CONTEXT_LENGTH] + "\n...(บริบทถูกตัดทอนเพื่อประหยัด tokens)"
            logger.info(f"⚠️ Context truncated to {MAX_CONTEXT_LENGTH} chars")
        
        prompt = f"""คำถาม: {query}

บริบท:
{context}

แหล่งข้อมูล: {', '.join(sources[:10])}{'...' if len(sources) > 10 else ''}

**กฎการตอบ:**
1. **ตีความคำถาม:** คำถามภาษาไทยอาจหมายถึงชื่อภาษาอังกฤษ (เช่น "เอนวิเดีย" = "NVIDIA"/"NVDA")
2. ถ้าบริบทมี**ความหมายเกี่ยวข้อง** กับคำถาม ให้ตอบจากบริบทนั้น แม้คำจะไม่ตรงทุกตัว
3. ถ้าบริบท**ไม่เกี่ยวข้องเลย** → ตอบว่า "ไม่พบข้อมูลเกี่ยวกับ '{query}'"
4. อย่าแต่งเรื่อง - ตอบเฉพาะที่มีในบริบท
5. ตอบสั้น กระชับ ตรงประเด็น

**ตัวอย่าง:**
- คำถาม: "เอนวิเดีย คืออะไร" + บริบท: "NVDA (Ticker Symbol) ของ NVIDIA Corporation" → ตอบ: "NVDA คือสัญลักษณ์หุ้น (Ticker Symbol) ของ NVIDIA Corporation บริษัทผู้ผลิต GPU"

คำตอบ:"""
        
        return await self.generate_content(prompt, temperature=0.5)

    async def infer_relationships(
        self,
        candidate_pairs: List[Dict[str, Any]],
        max_links: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Infer meaningful relationships between node pairs using background knowledge
        and semantic context, not only lexical overlap.
        """
        if not candidate_pairs:
            return []

        payload = candidate_pairs[:80]

        # Split pairs into vector-found (similarity > 0) and knowledge-only (similarity = 0)
        has_knowledge_only = any(p.get("similarity", 0) == 0.0 for p in payload)
        knowledge_note = (
            "\n⚠️  บาง pair มี similarity=0.0 หมายความว่ายังไม่มีข้อมูล embedding "
            "ให้ใช้ **ความรู้พื้นหลัง** ของคุณในการตัดสินว่าควรเชื่อมหรือไม่"
            if has_knowledge_only
            else ""
        )

        prompt = f"""คุณคือผู้ช่วยสร้าง Knowledge Graph แบบสมจริงเหมือนมนุษย์จดโน้ต{knowledge_note}

งานของคุณ:
1) พิจารณาคู่โหนดจากข้อมูลด้านล่าง
2) ตัดสินใจว่าควรเชื่อมกันหรือไม่ โดยใช้:
   - ความรู้เชิงความหมาย (semantic meaning)
   - ตรรกะของความรู้ (causal, compositional, contextual)
   - **ความรู้พื้นหลังทั่วไป** (background knowledge) — สำคัญมากสำหรับ pair ที่ similarity=0
3) อนุญาตความสัมพันธ์เชิงนามธรรม: เหตุ-ผล, ส่วนประกอบ, ตัวอย่างของ, สนับสนุน/ขัดแย้ง, ใช้ร่วมกัน
4) เลี่ยงลิงก์คลุมเครือ — ถ้าไม่แน่ใจจริงๆ ให้ข้าม
5) **สำคัญ**: โหนดจากหัวข้อต่างกันที่มีความเชื่อมโยงเชิงความรู้ควรเชื่อมกัน แม้ใช้คำต่างกัน

กฎผลลัพธ์ (ตอบ JSON เท่านั้น):
{{
  "links": [
    {{
      "source_id": "...",
      "target_id": "...",
      "label": "ความสัมพันธ์ไปข้างหน้า (สั้น ชัด ใช้คำกริยา)",
      "labelReverse": "ความสัมพันธ์ย้อนกลับ",
      "confidence": 0.0,
      "reason": "เหตุผล 1–2 ประโยคว่าทำไมถึงเชื่อมกัน"
    }}
  ]
}}
- confidence: 0–1 (ใช้ความรู้พื้นหลังด้วย ไม่ใช่แค่ similarity)
- เลือกไม่เกิน {max_links} ลิงก์ที่มั่นใจที่สุด
- ห้ามสร้าง ID ใหม่ ใช้เฉพาะ source_id/target_id ที่มีใน input

candidate_pairs:
{json.dumps(payload, ensure_ascii=False)}"""

        response_text = await self.generate_content(prompt=prompt, temperature=0.2)
        parsed = self._safe_json_parse(response_text)

        if not isinstance(parsed, dict):
            return []

        links = parsed.get("links", [])
        if not isinstance(links, list):
            return []

        normalized = []
        for item in links:
            if not isinstance(item, dict):
                continue
            source_id = str(item.get("source_id", "")).strip()
            target_id = str(item.get("target_id", "")).strip()
            if not source_id or not target_id:
                continue

            try:
                confidence = float(item.get("confidence", 0.0))
            except Exception:
                confidence = 0.0

            normalized.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "label": str(item.get("label", "เกี่ยวข้องกับ")).strip() or "เกี่ยวข้องกับ",
                    "labelReverse": str(item.get("labelReverse", "เกี่ยวข้องกับ")).strip() or "เกี่ยวข้องกับ",
                    "confidence": max(0.0, min(1.0, confidence)),
                    "reason": str(item.get("reason", "")).strip(),
                }
            )

        return normalized[:max_links]
    
    @staticmethod
    def _safe_json_parse(text: str) -> Optional[Any]:
        """Parse JSON from text, handling markdown code blocks"""
        if not text:
            return None
        
        try:
            # Try direct parse first
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from markdown code block
        import re
        json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try finding any JSON object or array
        json_match = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        logger.error(f"Failed to parse JSON from response: {text[:200]}")
        return None


# Global Gemini service instance
_gemini_service = None


def get_gemini_service() -> GeminiService:
    """Get singleton Gemini service instance"""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service

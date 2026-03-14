"""
Documents API - Handle document upload and parsing
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict
import logging

from app.services.document_parser import document_parser
from app.services.gemini_service import get_gemini_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/parse")
async def parse_document(file: UploadFile = File(...)) -> Dict:
    """
    Parse document (PDF/Word) and extract entities
    
    Args:
        file: Uploaded document file
        
    Returns:
        Dict with extracted text and entities
    """
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        if not (file.filename.lower().endswith('.pdf') or file.filename.lower().endswith('.docx')):
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Only PDF and DOCX are supported. Got: {file.filename}"
            )
        
        # Read file content
        file_content = await file.read()
        
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is 10MB. Got: {len(file_content) / (1024*1024):.1f}MB"
            )
        
        logger.info(f"📄 Parsing document: {file.filename} ({len(file_content)} bytes)")
        
        # Parse document to text
        extracted_text = await document_parser.parse_document(file_content, file.filename)
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from document. File may be empty or corrupted."
            )
        
        logger.info(f"✅ Extracted {len(extracted_text)} characters from {file.filename}")
        
        # Extract entities using Gemini
        logger.info("🤖 Extracting entities with AI...")
        gemini_service = get_gemini_service()
        entities = await gemini_service.extract_entities(extracted_text)
        
        logger.info(f"✅ Extracted {len(entities.get('nodes', []))} nodes and {len(entities.get('links', []))} links")
        
        return {
            "success": True,
            "filename": file.filename,
            "text_length": len(extracted_text),
            "full_text": extracted_text,
            "extracted_text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,  # Preview
            "entities": entities
        }
    
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"❌ Parsing error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Unexpected error parsing document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

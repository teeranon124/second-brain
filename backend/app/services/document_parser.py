"""
Document Parser Service - Extract text from PDF and Word documents
"""
import io
from typing import Optional
from pypdf import PdfReader
from docx import Document


class DocumentParserService:
    """Service for parsing PDF and Word documents"""
    
    async def parse_pdf(self, file_content: bytes) -> str:
        """
        Extract text from PDF file
        
        Args:
            file_content: PDF file bytes
            
        Returns:
            Extracted text content
        """
        try:
            pdf_reader = PdfReader(io.BytesIO(file_content))
            text_content = []
            
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
            
            return "\n\n".join(text_content)
        
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {str(e)}")
    
    async def parse_docx(self, file_content: bytes) -> str:
        """
        Extract text from Word document
        
        Args:
            file_content: Word file bytes
            
        Returns:
            Extracted text content
        """
        try:
            doc = Document(io.BytesIO(file_content))
            text_content = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text)
            
            return "\n\n".join(text_content)
        
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX: {str(e)}")
    
    async def parse_document(self, file_content: bytes, filename: str) -> str:
        """
        Auto-detect file type and parse accordingly
        
        Args:
            file_content: File bytes
            filename: Original filename
            
        Returns:
            Extracted text content
        """
        if filename.lower().endswith('.pdf'):
            return await self.parse_pdf(file_content)
        elif filename.lower().endswith('.docx'):
            return await self.parse_docx(file_content)
        else:
            raise ValueError(f"Unsupported file type: {filename}")


# Singleton instance
document_parser = DocumentParserService()

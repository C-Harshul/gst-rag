"""OCR processing functionality for PDFs that fail regular extraction and Textract."""

from pathlib import Path
from typing import List, Optional
from langchain_core.documents import Document
import tempfile
import os

try:
    from pdf2image import convert_from_path, convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class OCRProcessor:
    """Handles OCR processing for PDFs using Tesseract."""
    
    def __init__(self, tesseract_cmd: Optional[str] = None, dpi: int = 300):
        """
        Initialize OCR processor.
        
        Args:
            tesseract_cmd: Path to tesseract executable (if not in PATH)
            dpi: DPI for PDF to image conversion (higher = better quality, slower)
        """
        if not PDF2IMAGE_AVAILABLE:
            raise ImportError(
                "pdf2image is required for OCR. Install with: pip install pdf2image"
            )
        if not TESSERACT_AVAILABLE:
            raise ImportError(
                "pytesseract is required for OCR. Install with: pip install pytesseract"
            )
        
        self.dpi = dpi
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    
    def _check_tesseract_installed(self) -> bool:
        """Check if Tesseract OCR is installed on the system."""
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
    
    def extract_text_from_image(self, image) -> str:
        """
        Extract text from a PIL Image using Tesseract OCR.
        
        Args:
            image: PIL Image object
            
        Returns:
            Extracted text string
        """
        try:
            # Use Tesseract to extract text
            # Configure for better accuracy with documents
            custom_config = r'--oem 3 --psm 6'  # OCR Engine Mode 3, Page Segmentation Mode 6 (uniform block of text)
            text = pytesseract.image_to_string(image, config=custom_config)
            return text.strip()
        except Exception as e:
            raise Exception(f"Tesseract OCR failed: {str(e)}")
    
    def extract_text_from_pdf_file(self, file_path: str) -> str:
        """
        Extract text from a PDF file by converting pages to images and OCRing them.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Combined text from all pages
        """
        if not self._check_tesseract_installed():
            raise Exception(
                "Tesseract OCR is not installed. "
                "Install Tesseract: https://github.com/tesseract-ocr/tesseract"
            )
        
        try:
            print(f"Converting PDF to images (DPI: {self.dpi})...")
            # Convert PDF pages to images
            images = convert_from_path(file_path, dpi=self.dpi)
            print(f"Converted {len(images)} pages to images")
            
            # OCR each page
            all_text = []
            for i, image in enumerate(images, 1):
                print(f"OCR processing page {i}/{len(images)}...")
                page_text = self.extract_text_from_image(image)
                if page_text:
                    all_text.append(f"--- Page {i} ---\n{page_text}")
            
            combined_text = "\n\n".join(all_text)
            
            if not combined_text or len(combined_text.strip()) < 50:
                raise ValueError("OCR extracted insufficient text from PDF")
            
            print(f"✅ OCR extraction successful: {len(combined_text)} characters")
            return combined_text
            
        except Exception as e:
            raise Exception(f"OCR processing failed: {str(e)}")
    
    def extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """
        Extract text from PDF bytes by converting pages to images and OCRing them.
        
        Args:
            pdf_bytes: PDF file content as bytes
            
        Returns:
            Combined text from all pages
        """
        if not self._check_tesseract_installed():
            raise Exception(
                "Tesseract OCR is not installed. "
                "Install Tesseract: https://github.com/tesseract-ocr/tesseract"
            )
        
        try:
            print(f"Converting PDF bytes to images (DPI: {self.dpi})...")
            # Convert PDF pages to images
            images = convert_from_bytes(pdf_bytes, dpi=self.dpi)
            print(f"Converted {len(images)} pages to images")
            
            # OCR each page
            all_text = []
            for i, image in enumerate(images, 1):
                print(f"OCR processing page {i}/{len(images)}...")
                page_text = self.extract_text_from_image(image)
                if page_text:
                    all_text.append(f"--- Page {i} ---\n{page_text}")
            
            combined_text = "\n\n".join(all_text)
            
            if not combined_text or len(combined_text.strip()) < 50:
                raise ValueError("OCR extracted insufficient text from PDF")
            
            print(f"✅ OCR extraction successful: {len(combined_text)} characters")
            return combined_text
            
        except Exception as e:
            raise Exception(f"OCR processing failed: {str(e)}")
    
    def process_pdf_file(self, file_path: str, source_file: Optional[str] = None) -> List[Document]:
        """
        Process a PDF file using OCR and return Document objects.
        
        Args:
            file_path: Path to PDF file
            source_file: Original source file name for metadata
            
        Returns:
            List of Document objects (single document with all pages)
        """
        extracted_text = self.extract_text_from_pdf_file(file_path)
        
        doc = Document(
            page_content=extracted_text,
            metadata={
                'source_file': source_file or Path(file_path).name,
                'file_type': 'pdf',
                'document_type': 'gst_regulation',
                'extraction_method': 'ocr_tesseract'
            }
        )
        
        return [doc]
    
    def process_pdf_bytes(self, pdf_bytes: bytes, source_file: str) -> List[Document]:
        """
        Process PDF bytes using OCR and return Document objects.
        
        Args:
            pdf_bytes: PDF file content as bytes
            source_file: Source file name for metadata
            
        Returns:
            List of Document objects (single document with all pages)
        """
        extracted_text = self.extract_text_from_pdf_bytes(pdf_bytes)
        
        doc = Document(
            page_content=extracted_text,
            metadata={
                'source_file': source_file,
                'file_type': 'pdf',
                'document_type': 'gst_regulation',
                'extraction_method': 'ocr_tesseract'
            }
        )
        
        return [doc]


def is_ocr_available() -> bool:
    """Check if OCR dependencies are available."""
    return PDF2IMAGE_AVAILABLE and TESSERACT_AVAILABLE


def is_tesseract_installed() -> bool:
    """Check if Tesseract OCR is installed on the system."""
    if not TESSERACT_AVAILABLE:
        return False
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


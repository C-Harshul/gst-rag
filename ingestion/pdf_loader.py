"""PDF loading and chunking functionality for GST regulations."""

from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import tempfile
import os
import urllib.parse
import json

# Import OCR processor (optional dependency)
try:
    from ingestion.ocr_processor import OCRProcessor, is_ocr_available, is_tesseract_installed
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    OCRProcessor = None


class PDFLoader:
    """Handles PDF loading and text chunking for GST regulation documents."""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, ocr_dpi: int = 300):
        """
        Initialize PDF loader with chunking parameters.
        
        Args:
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            ocr_dpi: DPI for OCR processing (higher = better quality, slower)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )
        # Initialize OCR processor if available
        self.ocr_processor = None
        if OCR_AVAILABLE and is_ocr_available() and is_tesseract_installed():
            try:
                self.ocr_processor = OCRProcessor(dpi=ocr_dpi)
            except Exception as e:
                print(f"⚠️  OCR processor initialization failed: {str(e)}")
                self.ocr_processor = None
        
    def _extract_text_with_textract_s3(self, bucket: str, key: str) -> str:
        """
        Extract text from PDF in S3 using AWS Textract.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            Extracted text as a single string
        """
        print("⚠️  Regular PDF extraction failed. Attempting AWS Textract...")
        
        try:
            textract = boto3.client('textract')
            
            # Use Textract's S3 integration (more efficient than downloading)
            print(f"Calling Textract on s3://{bucket}/{key}")
            response = textract.detect_document_text(
                Document={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                }
            )
            
            # Extract text from Textract response
            text_lines = []
            for block in response.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    text_lines.append(block.get('Text', ''))
            
            extracted_text = '\n'.join(text_lines)
            print(f"✅ Textract extracted {len(extracted_text)} characters")
            
            return extracted_text
            
        except NoCredentialsError:
            raise Exception("AWS credentials not found. Cannot use Textract fallback.")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'AccessDenied':
                raise PermissionError(
                    f"Access denied to Textract or S3 object. "
                    f"Ensure IAM role has Textract and S3 permissions."
                )
            elif error_code == 'UnsupportedDocumentException':
                raise ValueError(
                    f"Textract does not support this PDF format. "
                    f"The PDF may be corrupted, password-protected, or in an unsupported format. "
                    f"Textract supports: PDF, PNG, JPEG, TIFF. "
                    f"Error: {str(e)}"
                )
            else:
                raise Exception(f"AWS Textract error ({error_code}): {str(e)}")
        except Exception as e:
            raise Exception(f"Textract extraction failed: {str(e)}")
    
    def _extract_text_with_textract_file(self, file_path: str) -> str:
        """
        Extract text from local PDF file using AWS Textract.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text as a single string
        """
        print("⚠️  Regular PDF extraction failed. Attempting AWS Textract...")
        
        try:
            textract = boto3.client('textract')
            
            # Read file and send to Textract
            with open(file_path, 'rb') as document:
                print(f"Calling Textract on local file: {file_path}")
                response = textract.detect_document_text(
                    Document={'Bytes': document.read()}
                )
            
            # Extract text from Textract response
            text_lines = []
            for block in response.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    text_lines.append(block.get('Text', ''))
            
            extracted_text = '\n'.join(text_lines)
            print(f"✅ Textract extracted {len(extracted_text)} characters")
            
            return extracted_text
            
        except NoCredentialsError:
            raise Exception("AWS credentials not found. Cannot use Textract fallback.")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'UnsupportedDocumentException':
                raise ValueError(
                    f"Textract does not support this PDF format. "
                    f"The PDF may be corrupted, password-protected, or in an unsupported format. "
                    f"Textract supports: PDF, PNG, JPEG, TIFF. "
                    f"Error: {str(e)}"
                )
            else:
                raise Exception(f"AWS Textract error ({error_code}): {str(e)}")
        except Exception as e:
            raise Exception(f"Textract extraction failed: {str(e)}")
    
    def _check_extraction_success(self, documents: List[Document], min_text_length: int = 100) -> bool:
        """
        Check if PDF extraction was successful (has meaningful text).
        
        Args:
            documents: List of extracted documents
            min_text_length: Minimum total text length to consider successful
            
        Returns:
            True if extraction appears successful, False otherwise
        """
        if not documents:
            return False
        
        # Calculate total text length
        total_text = "".join([doc.page_content.strip() for doc in documents])
        return len(total_text) >= min_text_length
    
    def load_from_file(self, file_path: str) -> List[Document]:
        """
        Load and chunk PDF from local file path.
        Falls back to AWS Textract if regular extraction fails (scanned PDFs).
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List of chunked documents
        """
        print(f"Loading PDF: {file_path}")
        
        # Try regular PDF text extraction first
        try:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    'source_file': Path(file_path).name,
                    'file_type': 'pdf',
                    'document_type': 'gst_regulation',
                    'extraction_method': 'pypdf'
                })
            
            # Check if extraction was successful
            if self._check_extraction_success(documents):
                # Split into chunks
                chunked_docs = self.text_splitter.split_documents(documents)
                print(f"✅ Regular extraction successful: {len(chunked_docs)} chunks")
                return chunked_docs
            else:
                print("⚠️  Regular extraction produced minimal text (likely scanned PDF)")
                raise ValueError("Insufficient text extracted")
                
        except Exception as e:
            print(f"Regular extraction failed: {str(e)}")
            # Fall back to Textract
            try:
                extracted_text = self._extract_text_with_textract_file(file_path)
                
                if not extracted_text or len(extracted_text.strip()) < 50:
                    raise ValueError("Textract also failed to extract meaningful text")
                
                # Create document from Textract output
                doc = Document(
                    page_content=extracted_text,
                    metadata={
                        'source_file': Path(file_path).name,
                        'file_type': 'pdf',
                        'document_type': 'gst_regulation',
                        'extraction_method': 'textract'
                    }
                )
                
                # Split into chunks
                chunked_docs = self.text_splitter.split_documents([doc])
                print(f"✅ Textract extraction successful: {len(chunked_docs)} chunks")
                return chunked_docs
                
            except ValueError as textract_error:
                # Textract doesn't support this format - try OCR as final fallback
                error_msg = str(textract_error)
                if self.ocr_processor:
                    print("⚠️  Textract failed. Attempting OCR as final fallback...")
                    try:
                        ocr_docs = self.ocr_processor.process_pdf_file(file_path, source_file=Path(file_path).name)
                        chunked_docs = self.text_splitter.split_documents(ocr_docs)
                        print(f"✅ OCR extraction successful: {len(chunked_docs)} chunks")
                        return chunked_docs
                    except Exception as ocr_error:
                        raise ValueError(
                            f"PDF extraction failed: Regular extraction produced no text, "
                            f"Textract cannot process this file format, and OCR also failed. "
                            f"Textract error: {error_msg}. OCR error: {str(ocr_error)}. "
                            f"The PDF may be corrupted, password-protected, or in an unsupported format."
                        )
                else:
                    raise ValueError(
                        f"PDF extraction failed: Regular extraction produced no text, "
                        f"and Textract cannot process this file format. "
                        f"{error_msg} "
                        f"The PDF may be corrupted, password-protected, or in an unsupported format. "
                        f"OCR is not available (install pdf2image, pytesseract, and Tesseract OCR)."
                    )
            except Exception as textract_error:
                # Textract failed with other error - try OCR as final fallback
                if self.ocr_processor:
                    print("⚠️  Textract failed. Attempting OCR as final fallback...")
                    try:
                        ocr_docs = self.ocr_processor.process_pdf_file(file_path, source_file=Path(file_path).name)
                        chunked_docs = self.text_splitter.split_documents(ocr_docs)
                        print(f"✅ OCR extraction successful: {len(chunked_docs)} chunks")
                        return chunked_docs
                    except Exception as ocr_error:
                        raise Exception(
                            f"All extraction methods failed. "
                            f"Regular error: {str(e)}, Textract error: {str(textract_error)}, "
                            f"OCR error: {str(ocr_error)}"
                        )
                else:
                    raise Exception(
                        f"Both regular extraction and Textract failed. "
                        f"Regular error: {str(e)}, Textract error: {str(textract_error)}. "
                        f"OCR is not available (install pdf2image, pytesseract, and Tesseract OCR)."
                    )
        
    def load_from_s3(self, bucket: str, key: str) -> List[Document]:
        """
        Load and chunk PDF from S3.
        Falls back to AWS Textract if regular extraction fails (scanned PDFs).
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            List of chunked documents
            
        Raises:
            Exception: If S3 download or PDF processing fails
        """
        s3_client = boto3.client('s3')
        tmp_file_path = None
        
        try:
            # URL decode the key in case it's encoded
            decoded_key = urllib.parse.unquote(key)
            
            print(f"Downloading from S3: bucket={bucket}, key={decoded_key}")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file_path = tmp_file.name
                # Use keyword arguments for clarity
                s3_client.download_fileobj(
                    Bucket=bucket,
                    Key=decoded_key,
                    Fileobj=tmp_file
                )
                tmp_file.flush()
                
                # Verify file was downloaded (check size)
                file_size = os.path.getsize(tmp_file_path)
                if file_size == 0:
                    raise ValueError(f"Downloaded file from s3://{bucket}/{decoded_key} is empty")
                
                print(f"Downloaded {file_size} bytes from S3")
                
                # Try regular extraction first
                try:
                    documents = self.load_from_file(tmp_file_path)
                    
                    # Add S3 metadata to documents
                    for doc in documents:
                        doc.metadata.update({
                            'source_bucket': bucket,
                            'source_key': decoded_key,
                        })
                    
                    return documents
                    
                except Exception as regular_error:
                    # Regular extraction failed, try Textract directly with S3
                    print(f"Regular extraction failed: {str(regular_error)}")
                    print("Attempting Textract with S3 object directly...")
                    
                    try:
                        extracted_text = self._extract_text_with_textract_s3(bucket, decoded_key)
                        
                        if not extracted_text or len(extracted_text.strip()) < 50:
                            raise ValueError("Textract also failed to extract meaningful text")
                        
                        # Create document from Textract output
                        doc = Document(
                            page_content=extracted_text,
                            metadata={
                                'source_file': Path(decoded_key).name,
                                'source_bucket': bucket,
                                'source_key': decoded_key,
                                'file_type': 'pdf',
                                'document_type': 'gst_regulation',
                                'extraction_method': 'textract'
                            }
                        )
                        
                        # Split into chunks
                        chunked_docs = self.text_splitter.split_documents([doc])
                        print(f"✅ Textract extraction successful: {len(chunked_docs)} chunks")
                        return chunked_docs
                        
                    except ValueError as textract_error:
                        # Textract doesn't support this format - try OCR as final fallback
                        error_msg = str(textract_error)
                        if self.ocr_processor:
                            print("⚠️  Textract failed. Attempting OCR as final fallback...")
                            try:
                                ocr_docs = self.ocr_processor.process_pdf_file(tmp_file_path, source_file=Path(decoded_key).name)
                                chunked_docs = self.text_splitter.split_documents(ocr_docs)
                                # Add S3 metadata
                                for doc in chunked_docs:
                                    doc.metadata.update({
                                        'source_bucket': bucket,
                                        'source_key': decoded_key,
                                    })
                                print(f"✅ OCR extraction successful: {len(chunked_docs)} chunks")
                                return chunked_docs
                            except Exception as ocr_error:
                                raise ValueError(
                                    f"PDF extraction failed: Regular extraction produced no text, "
                                    f"Textract cannot process this file format, and OCR also failed. "
                                    f"Textract error: {error_msg}. OCR error: {str(ocr_error)}. "
                                    f"The PDF may be corrupted, password-protected, or in an unsupported format."
                                )
                        else:
                            raise ValueError(
                                f"PDF extraction failed: Regular extraction produced no text, "
                                f"and Textract cannot process this file format. "
                                f"{error_msg} "
                                f"The PDF may be corrupted, password-protected, or in an unsupported format. "
                                f"OCR is not available (install pdf2image, pytesseract, and Tesseract OCR)."
                            )
                    except Exception as textract_error:
                        # Textract failed with other error - try OCR as final fallback
                        if self.ocr_processor:
                            print("⚠️  Textract failed. Attempting OCR as final fallback...")
                            try:
                                ocr_docs = self.ocr_processor.process_pdf_file(tmp_file_path, source_file=Path(decoded_key).name)
                                chunked_docs = self.text_splitter.split_documents(ocr_docs)
                                # Add S3 metadata
                                for doc in chunked_docs:
                                    doc.metadata.update({
                                        'source_bucket': bucket,
                                        'source_key': decoded_key,
                                    })
                                print(f"✅ OCR extraction successful: {len(chunked_docs)} chunks")
                                return chunked_docs
                            except Exception as ocr_error:
                                raise Exception(
                                    f"All extraction methods failed. "
                                    f"Regular error: {str(regular_error)}, Textract error: {str(textract_error)}, "
                                    f"OCR error: {str(ocr_error)}"
                                )
                        else:
                            raise Exception(
                                f"Both regular extraction and Textract failed. "
                                f"Regular error: {str(regular_error)}, Textract error: {str(textract_error)}. "
                                f"OCR is not available (install pdf2image, pytesseract, and Tesseract OCR)."
                            )
                
        except NoCredentialsError:
            raise Exception(f"AWS credentials not found. Please configure AWS credentials.")
        except (ValueError, FileNotFoundError, PermissionError) as e:
            # Propagate these specific exceptions as-is so API can return appropriate status codes
            raise
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchKey':
                raise FileNotFoundError(f"S3 object not found: s3://{bucket}/{key}")
            elif error_code == 'NoSuchBucket':
                raise ValueError(f"S3 bucket not found: {bucket}")
            elif error_code == 'AccessDenied':
                raise PermissionError(f"Access denied to s3://{bucket}/{key}. Check IAM permissions.")
            else:
                raise Exception(f"AWS S3 error ({error_code}): {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to load PDF from S3 (s3://{bucket}/{key}): {str(e)}")
        finally:
            # Clean up temporary file
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                except Exception as e:
                    print(f"Warning: Failed to delete temp file {tmp_file_path}: {e}")
            
    def extract_metadata(self, documents: List[Document]) -> Dict[str, Any]:
        """
        Extract metadata from loaded documents.
        
        Args:
            documents: List of documents
            
        Returns:
            Extracted metadata dictionary
        """
        if not documents:
            return {}
            
        return {
            'total_chunks': len(documents),
            'source': documents[0].metadata.get('source_file', 'unknown'),
            'total_characters': sum(len(doc.page_content) for doc in documents)
        }


# Utility functions for backward compatibility
def process_all_pdfs(pdf_directory: str) -> List[Document]:
    """Load all PDFs found under a directory (recursive), returning LangChain Documents."""
    loader = PDFLoader()
    all_documents = []
    pdf_dir = Path(pdf_directory)
    pdf_files = list(pdf_dir.glob("**/*.pdf"))
    print(f"Found {len(pdf_files)} PDF files to process")

    for pdf_file in pdf_files:
        try:
            documents = loader.load_from_file(str(pdf_file))
            all_documents.extend(documents)
            print(f"  ✓ Loaded {pdf_file.name}: {len(documents)} chunks")
        except Exception as e:
            print(f"  ✗ Error processing {pdf_file.name}: {e}")

    print(f"\nTotal chunks loaded: {len(all_documents)}")
    return all_documents


def split_documents(documents: List[Document], chunk_size=1000, chunk_overlap=200):
    """Split documents into chunks (for backward compatibility)."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )
    split_docs = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} documents into {len(split_docs)} chunks")
    if split_docs:
        print("Example chunk preview:")
        print(split_docs[0].page_content[:200], "...")
        print(split_docs[0].metadata)
    return split_docs
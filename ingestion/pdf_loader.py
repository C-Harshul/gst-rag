"""PDF loading and chunking functionality for GST regulations."""

from pathlib import Path
from typing import List, Dict, Any
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import tempfile
import os
import urllib.parse


class PDFLoader:
    """Handles PDF loading and text chunking for GST regulation documents."""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialize PDF loader with chunking parameters.
        
        Args:
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )
        
    def load_from_file(self, file_path: str) -> List[Document]:
        """
        Load and chunk PDF from local file path.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List of chunked documents
        """
        print(f"Loading PDF: {file_path}")
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        
        # Add metadata
        for doc in documents:
            doc.metadata.update({
                'source_file': Path(file_path).name,
                'file_type': 'pdf',
                'document_type': 'gst_regulation'
            })
        
        # Split into chunks
        chunked_docs = self.text_splitter.split_documents(documents)
        print(f"Split into {len(chunked_docs)} chunks")
        
        return chunked_docs
        
    def load_from_s3(self, bucket: str, key: str) -> List[Document]:
        """
        Load and chunk PDF from S3.
        
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
                
                documents = self.load_from_file(tmp_file_path)
                
                # Add S3 metadata to documents
                for doc in documents:
                    doc.metadata.update({
                        'source_bucket': bucket,
                        'source_key': decoded_key,
                    })
                    
                return documents
                
        except NoCredentialsError:
            raise Exception(f"AWS credentials not found. Please configure AWS credentials.")
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
"""AWS Lambda entrypoint for S3 trigger-based PDF ingestion."""

import json
import boto3
from typing import Dict, Any

# Import the same components used by ingest_documents.py
from ingestion.pdf_loader import PDFLoader
from ingestion.embeddings import cf_embedder, GSTEmbeddings
from rag.vectorstore import get_vectorstore, add_documents_safely


def process_s3_pdf(bucket: str, key: str) -> Dict[str, Any]:
    """
    Process a PDF from S3 through the complete ingestion pipeline.
    Same logic as ingest_documents.py but for S3 files.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        
    Returns:
        Processing results and metadata
    """
    print(f"Processing S3 PDF: s3://{bucket}/{key}")
    
    # Initialize components (same as ingest_documents.py)
    pdf_loader = PDFLoader()
    embeddings = GSTEmbeddings(cf_embedder)
    vectorstore = get_vectorstore(cf_embedder)
    
    try:
        # Load and chunk PDF directly from S3
        print("Loading and chunking PDF from S3...")
        documents = pdf_loader.load_from_s3(bucket, key)
        print(f"Created {len(documents)} chunks")
        
        # Add to vector store safely (embeddings will be generated automatically by LangChain)
        print("Adding to vector store...")
        total_added = add_documents_safely(vectorstore, documents)
        
        print(f"✅ Successfully ingested {total_added} chunks from s3://{bucket}/{key}")
        
        return {
            'status': 'success',
            'chunks_processed': total_added,
            's3_location': f's3://{bucket}/{key}',
            'metadata': pdf_loader.extract_metadata(documents)
        }
        
    except Exception as e:
        print(f"❌ Error processing s3://{bucket}/{key}: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            's3_location': f's3://{bucket}/{key}'
        }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for S3 object creation events.
    
    Args:
        event: S3 event data containing bucket and object information
        context: Lambda context object
        
    Returns:
        Response dictionary with status and message
    """
    try:
        # Parse S3 event
        records = event.get('Records', [])
        results = []
        
        for record in records:
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            
            # Only process PDF files
            if not key.lower().endswith('.pdf'):
                print(f"Skipping non-PDF file: {key}")
                continue
                
            # Process the PDF using the same logic as ingest_documents.py
            result = process_s3_pdf(bucket, key)
            results.append(result)
            
        # Count successful processing
        successful = sum(1 for r in results if r['status'] == 'success')
        total_chunks = sum(r.get('chunks_processed', 0) for r in results if r['status'] == 'success')
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {successful}/{len(results)} files',
                'total_chunks_ingested': total_chunks,
                'processed_files': [r['s3_location'] for r in results],
                'results': results
            })
        }
        
    except Exception as e:
        print(f"Lambda handler error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Failed to process S3 trigger'
            })
        }

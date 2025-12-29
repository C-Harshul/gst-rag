"""Script to clean up/delete collections from ChromaDB."""

import os
import sys
import chromadb
from chromadb.config import Settings

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Get ChromaDB connection settings
CHROMA_HOST = os.getenv("CHROMA_HOST", None)
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))


def get_chroma_client():
    """Get ChromaDB client with multiple connection attempts."""
    if not CHROMA_HOST:
        raise ValueError(
            "CHROMA_HOST environment variable is not set. "
            "Please set CHROMA_HOST to connect to ChromaDB server."
        )
    
    connection_methods = [
        # Method 1: Try with tenant/database parameters
        {
            "name": "with tenant/database parameters",
            "client": lambda: chromadb.HttpClient(
                host=CHROMA_HOST,
                port=CHROMA_PORT,
                tenant="default_tenant",
                database="default_database"
            )
        },
        # Method 2: Try with Settings and explicit tenant/database
        {
            "name": "with Settings and tenant/database",
            "client": lambda: chromadb.HttpClient(
                host=CHROMA_HOST,
                port=CHROMA_PORT,
                settings=Settings(
                    tenant="default_tenant",
                    database="default_database",
                    anonymized_telemetry=False
                )
            )
        },
        # Method 3: Try without any tenant/database
        {
            "name": "without tenant/database",
            "client": lambda: chromadb.HttpClient(
                host=CHROMA_HOST,
                port=CHROMA_PORT
            )
        },
        # Method 4: Try with Settings but no tenant/database
        {
            "name": "with Settings (no tenant)",
            "client": lambda: chromadb.HttpClient(
                host=CHROMA_HOST,
                port=CHROMA_PORT,
                settings=Settings(anonymized_telemetry=False)
            )
        }
    ]
    
    for method in connection_methods:
        try:
            client = method["client"]()
            # Test connection
            _ = client.list_collections()
            print(f"✓ Connected to ChromaDB server at {CHROMA_HOST}:{CHROMA_PORT} ({method['name']})")
            return client
        except Exception as e:
            continue
    
    raise ConnectionError(
        f"Failed to connect to ChromaDB server at {CHROMA_HOST}:{CHROMA_PORT}"
    )


def delete_collection(collection_name: str):
    """
    Delete a collection from ChromaDB.
    
    Args:
        collection_name: Name of the collection to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_chroma_client()
        
        # Check if collection exists
        collections = client.list_collections()
        collection_names = [col.name for col in collections]
        
        if collection_name not in collection_names:
            print(f"ℹ️  Collection '{collection_name}' does not exist.")
            return False
        
        # Get collection info before deletion
        collection = client.get_collection(collection_name)
        doc_count = collection.count()
        
        print(f"Found collection '{collection_name}' with {doc_count} documents")
        
        # Confirm deletion
        response = input(f"Are you sure you want to delete collection '{collection_name}'? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Deletion cancelled.")
            return False
        
        # Delete the collection
        client.delete_collection(collection_name)
        print(f"✅ Successfully deleted collection '{collection_name}' ({doc_count} documents removed)")
        return True
        
    except Exception as e:
        print(f"❌ Error deleting collection '{collection_name}': {str(e)}")
        return False


def clear_collection(collection_name: str):
    """
    Clear all documents from a collection without deleting the collection itself.
    
    Args:
        collection_name: Name of the collection to clear
        
    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_chroma_client()
        
        # Check if collection exists
        collections = client.list_collections()
        collection_names = [col.name for col in collections]
        
        if collection_name not in collection_names:
            print(f"ℹ️  Collection '{collection_name}' does not exist.")
            return False
        
        # Get collection and all document IDs
        collection = client.get_collection(collection_name)
        results = collection.get()
        
        if not results['ids']:
            print(f"ℹ️  Collection '{collection_name}' is already empty.")
            return True
        
        doc_count = len(results['ids'])
        print(f"Found {doc_count} documents in collection '{collection_name}'")
        
        # Confirm clearing
        response = input(f"Are you sure you want to clear all documents from '{collection_name}'? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Clear operation cancelled.")
            return False
        
        # Delete all documents
        collection.delete(ids=results['ids'])
        print(f"✅ Successfully cleared {doc_count} documents from collection '{collection_name}'")
        return True
        
    except Exception as e:
        print(f"❌ Error clearing collection '{collection_name}': {str(e)}")
        return False


def list_collections():
    """List all collections in ChromaDB."""
    try:
        client = get_chroma_client()
        collections = client.list_collections()
        
        if not collections:
            print("ℹ️  No collections found.")
            return
        
        print(f"\nFound {len(collections)} collection(s):")
        print("-" * 60)
        for col in collections:
            try:
                doc_count = col.count()
                print(f"  • {col.name}: {doc_count} documents")
            except:
                print(f"  • {col.name}: (unable to get count)")
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ Error listing collections: {str(e)}")


def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python cleanup_collection.py list                    # List all collections")
        print("  python cleanup_collection.py delete <collection>    # Delete a collection")
        print("  python cleanup_collection.py clear <collection>     # Clear documents from a collection")
        print("\nExample:")
        print("  python cleanup_collection.py delete Cases")
        print("  python cleanup_collection.py clear Cases")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_collections()
    elif command == "delete":
        if len(sys.argv) < 3:
            print("❌ Error: Please specify collection name")
            print("Usage: python cleanup_collection.py delete <collection_name>")
            return
        collection_name = sys.argv[2]
        delete_collection(collection_name)
    elif command == "clear":
        if len(sys.argv) < 3:
            print("❌ Error: Please specify collection name")
            print("Usage: python cleanup_collection.py clear <collection_name>")
            return
        collection_name = sys.argv[2]
        clear_collection(collection_name)
    else:
        print(f"❌ Unknown command: {command}")
        print("Available commands: list, delete, clear")


if __name__ == "__main__":
    main()


import os
import time
import chromadb
from chromadb.config import Settings
from langchain_community.vectorstores import Chroma
from ingestion.embeddings import GSTEmbeddings
from config.settings import COLLECTION_NAME, CHROMA_PERSIST_DIR


# =========================
# Configuration
# =========================

# Remote ChromaDB server configuration (required)
# Set CHROMA_HOST environment variable to connect to remote ChromaDB server
CHROMA_HOST = os.getenv("CHROMA_HOST", None)  # e.g., "44.211.29.171"
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))


# =========================
# Safe batched ingestion
# =========================

def add_documents_safely(
    vector_store,
    documents,
    batch_size: int = 20,
    max_retries: int = 3,
):
    """
    Add documents to Chroma in batches with retries.
    Works correctly with Chroma Server (HTTP mode).
    """

    if not documents:
        print("No documents to add.")
        return 0

    print(
        f"Adding {len(documents)} documents "
        f"in batches of {batch_size}..."
    )

    total_added = 0

    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i : i + batch_size]

        for attempt in range(1, max_retries + 1):
            try:
                vector_store.add_documents(batch_docs)
                total_added += len(batch_docs)

                print(
                    f"✓ Batch {i // batch_size + 1} "
                    f"added ({len(batch_docs)} docs) "
                    f"[total: {total_added}/{len(documents)}]"
                )
                break

            except Exception as e:
                if attempt == max_retries:
                    print(
                        f"❌ Failed batch {i // batch_size + 1} "
                        f"after {max_retries} attempts"
                    )
                    raise

                print(
                    f"⚠️  Batch {i // batch_size + 1} failed "
                    f"(attempt {attempt}/{max_retries}). Retrying..."
                )
                time.sleep(2 ** attempt)

        # small pause to reduce load
        time.sleep(0.2)

    print(f"\n✅ Successfully added {total_added} documents.")
    return total_added


# =========================
# Vectorstore factory
# =========================

def get_vectorstore(embedding_client, force_refresh=False):
    """
    Always returns a fresh LangChain Chroma wrapper
    connected to the Chroma SERVER (not embedded).
    
    Args:
        embedding_client: The embedding client to use
        force_refresh: If True, forces a fresh connection (default: False)
    """

    embeddings = GSTEmbeddings(embedding_client)

    # Connect to ChromaDB server - CHROMA_HOST must be configured
    if not CHROMA_HOST:
        raise ValueError(
            "CHROMA_HOST environment variable is not set. "
            "Please set CHROMA_HOST to connect to ChromaDB server."
        )
    
    client = None
    last_error = None
    
    # Try to create HTTP client - ChromaDB may require tenant/database to be created first
    # Try multiple approaches to connect
    # First, try to create/get tenant using AdminClient if available
    try:
        admin_client = chromadb.AdminClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT
        )
        # Try to create tenant and database if they don't exist
        try:
            admin_client.create_tenant("default_tenant")
        except Exception:
            pass  # Tenant might already exist
        try:
            admin_client.create_database("default_database", tenant="default_tenant")
        except Exception:
            pass  # Database might already exist
    except Exception:
        pass  # AdminClient might not be available, continue with regular client
    
    connection_methods = [
            # Method 1: Try with just tenant/database parameters (most common)
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
            # Method 3: Try without any tenant/database (for servers without multi-tenancy)
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
                # Test connection by listing collections (this validates the connection)
                _ = client.list_collections()
                print(f"✓ Connected to ChromaDB server at {CHROMA_HOST}:{CHROMA_PORT} ({method['name']})")
                break
            except Exception as e:
                last_error = str(e)
                continue
        
    if client is None:
        # All connection attempts failed - raise an error
        error_details = last_error[:500] if last_error else 'Unknown error'
        raise ConnectionError(
            f"Failed to connect to ChromaDB server at {CHROMA_HOST}:{CHROMA_PORT}.\n"
            f"Tried {len(connection_methods)} connection methods, all failed.\n"
            f"Last error: {error_details}\n"
            f"Please ensure:\n"
            f"  1. ChromaDB server is running and accessible\n"
            f"  2. Tenant 'default_tenant' and database 'default_database' exist on the server\n"
            f"  3. Network connectivity and security groups allow connections on port {CHROMA_PORT}"
        )

    # Optional sanity check - this also helps refresh the connection
    try:
        # Always get a fresh collection reference to avoid caching
        collection = client.get_collection(COLLECTION_NAME)
        if force_refresh:
            # Force a fresh read from disk by:
            # 1. Getting a new collection reference
            # 2. Calling count() which forces a database query
            # 3. This ensures we see the latest documents
            collection = client.get_collection(COLLECTION_NAME)
            doc_count = collection.count()  # Forces a fresh database read
            print(
                f"Connected to collection '{COLLECTION_NAME}' "
                f"({doc_count} documents) [fresh read]"
            )
        else:
            doc_count = collection.count()
            print(
                f"Connected to collection '{COLLECTION_NAME}' "
                f"({doc_count} documents)"
            )
    except Exception:
        print(
            f"Collection '{COLLECTION_NAME}' not found. "
            f"It will be created on first write."
        )

    # Create a fresh Chroma instance to avoid any caching
    # Each time this is called, it creates a new wrapper that will
    # query the server/disk for the latest data
    max_retries = 2
    for attempt in range(max_retries):
        try:
            # When force_refresh is True, we need to ensure the Chroma wrapper
            # doesn't cache the collection. We do this by creating a completely
            # fresh wrapper each time.
            vectorstore = Chroma(
                client=client,
                collection_name=COLLECTION_NAME,
                embedding_function=embeddings,
            )
            
            # If force_refresh, ensure the vectorstore has a fresh collection reference
            if force_refresh:
                # Force the vectorstore to refresh by re-initializing its collection
                # The Chroma wrapper caches the collection in _collection, so we need
                # to ensure it gets a fresh reference
                try:
                    # Access the collection through the client to force a fresh read
                    fresh_collection = client.get_collection(COLLECTION_NAME)
                    # Update the vectorstore's internal collection reference
                    vectorstore._collection = fresh_collection
                    # Verify we can get a fresh count
                    _ = fresh_collection.count()
                except (AttributeError, Exception) as e:
                    # If we can't update _collection, that's okay - the wrapper
                    # should still work, but might use cached data
                    # Log a warning in debug mode
                    pass
            
            return vectorstore
        except Exception as e:
            # Re-raise the error - no local database fallback
            if attempt == max_retries - 1:
                raise RuntimeError(
                    f"Failed to create vectorstore after {max_retries} attempts. "
                    f"Error: {str(e)}"
                )
            # Retry on next attempt
            continue
    
    # Should not reach here, but just in case
    raise RuntimeError("Failed to create vectorstore after retries")

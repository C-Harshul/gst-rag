from rag.vectorstore import get_vectorstore

def get_retriever(embedding_client, k: int = 4, force_refresh=False):
    """
    Get a retriever from the vectorstore.
    
    Args:
        embedding_client: The embedding client to use
        k: Number of documents to retrieve (default: 4)
        force_refresh: If True, forces a fresh connection to avoid caching (default: False)
    """
    vectordb = get_vectorstore(embedding_client, force_refresh=force_refresh)
    return vectordb.as_retriever(search_kwargs={"k": k})

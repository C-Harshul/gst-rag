import os
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage

from rag.retriever import get_retriever
from rag.prompt import RAG_PROMPT

##LangSmith
os.environ["LANGCHAIN_TRACING_V2"]="true"
os.environ["LANGCHAIN_API_KEY"]=os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"]=os.getenv("LANGCHAIN_PROJECT", "gst-rag-system")


def extract_date_from_metadata(doc) -> Optional[str]:
    """
    Extract date from document metadata or filename.
    
    Args:
        doc: Document object with metadata
        
    Returns:
        Date string if found, None otherwise
    """
    if not hasattr(doc, 'metadata'):
        return None
    
    metadata = doc.metadata
    
    # Try to get date from metadata
    if 'date' in metadata:
        return str(metadata['date'])
    
    # Try to extract date from filename
    filename = metadata.get('source_file', '') or metadata.get('source', '')
    if filename:
        # Look for date patterns in filename (YYYY-MM-DD, YYYY/MM/DD, etc.)
        date_patterns = [
            r'(\d{4}[-/]\d{2}[-/]\d{2})',  # YYYY-MM-DD or YYYY/MM/DD
            r'(\d{4}[-/]\d{2})',  # YYYY-MM or YYYY/MM
            r'(\d{4})',  # YYYY
        ]
        for pattern in date_patterns:
            match = re.search(pattern, filename)
            if match:
                return match.group(1)
    
    # Try to get date from S3 key path (often contains dates)
    s3_key = metadata.get('source_key', '')
    if s3_key:
        date_patterns = [
            r'(\d{4}[-/]\d{2}[-/]\d{2})',
            r'(\d{4}[-/]\d{2})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, s3_key)
            if match:
                return match.group(1)
    
    return None


def format_document_citation(doc, collection_name: str, doc_index: int, include_line_number: bool = False) -> str:
    """
    Format a detailed citation for a document including date and page number.
    Returns citation as a footnote-style reference below the content.
    
    Args:
        doc: Document object with metadata
        collection_name: Name of the collection (e.g., "EY-Papers", "Cases", "Bare-Law")
        doc_index: Index of the document in the retrieval results
        include_line_number: If True, includes line number in citation (for Bare-Law)
        
    Returns:
        Formatted citation string to appear below content
    """
    citation_parts = []
    
    # Add document name
    filename = None
    if hasattr(doc, 'metadata'):
        filename = doc.metadata.get('source_file') or doc.metadata.get('source', '')
        if filename:
            # Clean up filename (remove path, keep just name)
            filename = filename.split('/')[-1]
            citation_parts.append(f"Document: {filename}")
    
    # Add date
    date = extract_date_from_metadata(doc)
    if date:
        citation_parts.append(f"Date: {date}")
    
    # Add page number
    page = None
    if hasattr(doc, 'metadata') and 'page' in doc.metadata:
        page = doc.metadata.get('page')
        if page is not None:
            citation_parts.append(f"Page: {page + 1}")  # Convert 0-indexed to 1-indexed
    
    # Add line number for Bare-Law collection
    if include_line_number:
        line_num = None
        if hasattr(doc, 'metadata'):
            # Try to get line number from metadata
            line_num = doc.metadata.get('line_number') or doc.metadata.get('line')
            if line_num is None and hasattr(doc, 'page_content'):
                # Calculate approximate line number from content position
                # This is an approximation - assumes content starts at beginning of page
                content_lines = doc.page_content.split('\n')
                if content_lines:
                    # Estimate line number based on first non-empty line
                    for idx, line in enumerate(content_lines[:5], 1):
                        if line.strip():
                            line_num = idx
                            break
                    if line_num is None:
                        line_num = 1
        if line_num is not None:
            citation_parts.append(f"Line: {line_num}")
    
    # Format as reference
    citation_text = ", ".join(citation_parts) if citation_parts else "Unknown source"
    return f"[{doc_index}] {collection_name} Collection - {citation_text}"


def extract_case_numbers(context: str, llm=None) -> List[str]:
    """
    Extract case numbers from the EY-Papers context.
    Uses both regex patterns and LLM-based extraction for better accuracy.
    
    Args:
        context: The context text from EY-Papers collection
        llm: Optional LLM for intelligent extraction (if None, uses regex only)
        
    Returns:
        List of extracted case numbers/identifiers
    """
    case_numbers = []
    
    # Method 1: Regex patterns for common case number formats
    patterns = [
        r'Case\s+No\.?\s*:?\s*([A-Z0-9/\-]+)',
        r'Case\s+Number\s*:?\s*([A-Z0-9/\-]+)',
        r'CIT\s+v\.?\s+([A-Za-z0-9\s]+)',
        r'W\.P\.\s+No\.?\s*:?\s*([A-Z0-9/\-]+)',
        r'Writ\s+Petition\s+No\.?\s*:?\s*([A-Z0-9/\-]+)',
        r'([A-Z]{2,}\s+v\.?\s+[A-Za-z0-9\s]+)',  # Generic case format like "ABC v. XYZ"
        r'([0-9]{4})\s+[A-Z]{2,}',  # Year followed by abbreviation
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, context, re.IGNORECASE)
        case_numbers.extend(matches)
    
    # Method 2: Use LLM for intelligent extraction if available
    if llm and len(context) > 100:  # Only use LLM for substantial context
        try:
            # Limit to first 2000 chars to avoid token limits
            limited_context = context[:2000]
            extraction_prompt = f"""Extract all case numbers, case names, or case identifiers from the following text.
Return only the case identifiers, one per line. Examples: "CIT v. ABC Ltd", "W.P. No. 123/2020", "Case No. 456".

Text:
{limited_context}

Case numbers/identifiers:"""
            
            llm_result = llm.invoke(extraction_prompt)
            # Parse LLM output - split by newlines and clean
            llm_cases = [line.strip() for line in str(llm_result).split('\n') if line.strip()]
            case_numbers.extend(llm_cases)
            print(f"LLM extracted {len(llm_cases)} case numbers")
        except Exception as e:
            print(f"LLM extraction failed, using regex only: {str(e)}")
    
    # Remove duplicates and clean up
    case_numbers = list(set([cn.strip() for cn in case_numbers if cn.strip() and len(cn.strip()) > 2]))
    
    print(f"Total extracted case numbers: {case_numbers}")
    return case_numbers


def multi_collection_retrieval(input_dict: Dict[str, Any], ey_papers_retriever, cases_retriever, llm=None) -> Dict[str, Any]:
    """
    Two-step retrieval process with source tracking:
    1. Fetch from EY-Papers collection
    2. Extract case numbers
    3. Fetch from Cases collection using case numbers
    4. Combine contexts with clear source labels
    
    Args:
        input_dict: Dictionary containing the question
        ey_papers_retriever: Retriever for EY-Papers collection
        cases_retriever: Retriever for Cases collection
        llm: Optional LLM for case number extraction
        
    Returns:
        Dictionary with combined context, question, and source counts
    """
    question = input_dict.get("question", "")
    
    # Step 1: Retrieve from EY-Papers collection
    print("Step 1: Retrieving from EY-Papers collection...")
    # Use invoke() which is the standard method for runnables
    ey_papers_docs = ey_papers_retriever.invoke(question)
    
    # Ensure it's a list
    if not isinstance(ey_papers_docs, list):
        ey_papers_docs = [ey_papers_docs] if ey_papers_docs else []
    
    # Add source metadata to each document with citations below content
    # Use sequential numbering starting from 1
    ey_papers_context_parts = []
    ref_counter = 1
    for doc in ey_papers_docs:
        citation = format_document_citation(doc, "EY-Papers", ref_counter)
        # Put content first, then citation below for readability
        ey_papers_context_parts.append(f"{doc.page_content}\n\nReference: {citation}")
        ref_counter += 1
    
    ey_papers_context = "\n\n---\n\n".join(ey_papers_context_parts)
    print(f"Retrieved {len(ey_papers_docs)} documents from EY-Papers")
    
    # Step 2: Extract case numbers from EY-Papers context
    print("Step 2: Extracting case numbers...")
    case_numbers = extract_case_numbers(ey_papers_context, llm=llm)
    
    # Step 3: Retrieve from Cases collection using case numbers
    cases_context = ""
    cases_context_parts = []
    cases_doc_count = 0
    if case_numbers:
        print(f"Step 3: Retrieving from Cases collection using case numbers: {case_numbers}")
        # Create a search query that includes the case numbers
        case_search_query = f"{question} {' '.join(case_numbers)}"
        # Use invoke() which is the standard method for runnables
        cases_docs = cases_retriever.invoke(case_search_query)
        
        # Ensure it's a list
        if not isinstance(cases_docs, list):
            cases_docs = [cases_docs] if cases_docs else []
        
        # Add source metadata to each document with citations below content
        # Continue sequential numbering from EY-Papers
        for doc in cases_docs:
            citation = format_document_citation(doc, "Cases", ref_counter)
            # Put content first, then citation below for readability
            cases_context_parts.append(f"{doc.page_content}\n\nReference: {citation}")
            ref_counter += 1
        
        cases_context = "\n\n---\n\n".join(cases_context_parts)
        cases_doc_count = len(cases_docs)
        print(f"Retrieved {cases_doc_count} documents from Cases collection")
    else:
        print("Step 3: No case numbers found, skipping Cases collection retrieval")
    
    # Step 4: Combine contexts with clear section headers
    if cases_context:
        combined_context = f"""=== EY-Papers Collection ===
{ey_papers_context}

=== Cases Collection ===
{cases_context}"""
    else:
        combined_context = f"""=== EY-Papers Collection ===
{ey_papers_context}"""
    
    print(f"Combined context length: {len(combined_context)} characters")
    
    return {
        "context": combined_context,
        "question": question,
        "sources": {
            "EY-Papers": len(ey_papers_docs),
            "Cases": cases_doc_count
        }
    }


def format_conversation_history(history: List[Tuple[str, str]]) -> str:
    """
    Format conversation history for inclusion in the prompt.
    
    Args:
        history: List of (question, answer) tuples
        
    Returns:
        Formatted conversation history string
    """
    if not history:
        return "No previous conversation in this session."
    
    formatted_history = []
    for i, (question, answer) in enumerate(history, 1):
        formatted_history.append(f"Previous Question {i}: {question}")
        formatted_history.append(f"Previous Answer {i}: {answer}")
    
    return "\n\n".join(formatted_history)


def format_bare_law_citation_with_lines(doc, doc_index: int) -> str:
    """
    Format a detailed citation for Bare-Law collection with line-by-line references.
    Each line in the content is quoted with its citation.
    
    Args:
        doc: Document object with metadata
        doc_index: Index of the document in the retrieval results
        
    Returns:
        Formatted citation string with line-by-line quotes
    """
    citation_parts = []
    
    # Get document name
    filename = None
    if hasattr(doc, 'metadata'):
        filename = doc.metadata.get('source_file') or doc.metadata.get('source', '')
        if filename:
            filename = filename.split('/')[-1]
            citation_parts.append(f"Document: {filename}")
    
    # Get page number
    page = None
    if hasattr(doc, 'metadata') and 'page' in doc.metadata:
        page = doc.metadata.get('page')
        if page is not None:
            page = page + 1  # Convert 0-indexed to 1-indexed
            citation_parts.append(f"Page: {page}")
    
    # Format base citation
    base_citation = ", ".join(citation_parts) if citation_parts else "Unknown source"
    
    # Format content with line-by-line citations
    if hasattr(doc, 'page_content') and doc.page_content:
        lines = doc.page_content.split('\n')
        formatted_lines = []
        
        # Try to get starting line number from metadata
        start_line = 1
        if hasattr(doc, 'metadata'):
            start_line = doc.metadata.get('start_line') or doc.metadata.get('line_start') or 1
            try:
                start_line = int(start_line)
            except (ValueError, TypeError):
                start_line = 1
        
        current_line_num = start_line
        
        for line in lines:
            if line.strip():  # Only include non-empty lines
                # Quote the line and add citation with book name
                quoted_line = f'"{line.strip()}"'
                # Format: [ref] Bare-Law Book - Document: filename, Page: X, Line: Y
                line_citation = f"[{doc_index}] Bare-Law Book - {base_citation}, Line: {current_line_num}"
                formatted_lines.append(f"{quoted_line}\n{line_citation}")
                current_line_num += 1
        
        return "\n\n".join(formatted_lines)
    
    # Fallback if no content
    return f"[{doc_index}] Bare-Law Book - {base_citation}"


def is_direct_factual_question(question: str) -> bool:
    """
    Determine if a question is a direct factual question that should use the 'in detail' query enhancement.
    
    Args:
        question: The question string
        
    Returns:
        True if it's a direct factual question, False otherwise
    """
    question_lower = question.lower().strip()
    
    # Patterns that indicate direct factual questions
    direct_question_patterns = [
        r'^what is',
        r'^what are',
        r'^what does',
        r'^what do',
        r'^explain',
        r'^define',
        r'^describe',
        r'^tell me about',
        r'^what is section',
        r'^what are the',
        r'^what does section',
        r'^how is',
        r'^how are',
        r'^who is',
        r'^who are',
        r'^when is',
        r'^when are',
        r'^where is',
        r'^where are',
    ]
    
    for pattern in direct_question_patterns:
        if re.match(pattern, question_lower):
            return True
    
    return False


def smart_assistant_retrieval(input_dict: Dict[str, Any], handbook_retriever, bare_law_retriever, llm=None) -> Dict[str, Any]:
    """
    Smart assistant retrieval process:
    1. Check Handbook collection for relevant context (for reasoning only, NOT for citations)
    2. If useful context found, use it for understanding the topic
    3. Retrieve line-by-line clauses from Bare-Law collection (for citations only)
    4. Format Bare-Law with exact page number and line citations with quotes
    
    Args:
        input_dict: Dictionary containing the question
        handbook_retriever: Retriever for Handbook collection (used for reasoning only)
        bare_law_retriever: Retriever for Bare-Law collection (used for citations)
        llm: Optional LLM for relevance checking
        
    Returns:
        Dictionary with combined context, question, and source counts
        Note: Handbook context is included without citations, Bare-Law context includes citations
    """
    question = input_dict.get("question", "")
    
    # Step 1: Check Handbook collection for relevant context
    print("Step 1: Checking Handbook collection for relevant context...")
    handbook_docs = handbook_retriever.invoke(question)
    
    # Ensure it's a list
    if not isinstance(handbook_docs, list):
        handbook_docs = [handbook_docs] if handbook_docs else []
    
    handbook_context = ""
    handbook_context_parts = []
    ref_counter = 1
    
    if handbook_docs:
        print(f"Found {len(handbook_docs)} relevant documents in Handbook collection")
        
        # Use LLM to check if the handbook context is useful
        if llm and len(handbook_docs) > 0:
            # Combine handbook content for relevance check
            handbook_text = "\n\n".join([doc.page_content for doc in handbook_docs[:3]])
            relevance_prompt = f"""Given the following question and context from a handbook, determine if the handbook context is useful and relevant for answering the question.

Question: {question}

Handbook Context:
{handbook_text[:2000]}

Is this handbook context useful and relevant? Answer with just 'YES' or 'NO'."""
            
            try:
                relevance_check = llm.invoke(relevance_prompt)
                is_relevant = "YES" in str(relevance_check).upper()
                print(f"Handbook relevance check: {'RELEVANT' if is_relevant else 'NOT RELEVANT'}")
            except Exception as e:
                print(f"Relevance check failed, assuming relevant: {str(e)}")
                is_relevant = True
        else:
            is_relevant = True  # Assume relevant if no LLM available
        
        if is_relevant:
            # Format handbook context WITHOUT citations - only for reasoning
            for doc in handbook_docs:
                handbook_context_parts.append(doc.page_content)
            
            handbook_context = "\n\n---\n\n".join(handbook_context_parts)
            print("Using Handbook context for reasoning (not for citations)")
        else:
            print("Handbook context not relevant, skipping")
    else:
        print("No relevant documents found in Handbook collection")
    
    # Step 2: Retrieve from Bare-Law collection with line-by-line citations
    print("Step 2: Retrieving line-by-line clauses from Bare-Law collection...")
    
    # For direct factual questions, create an enhanced query with "in detail" appended
    if is_direct_factual_question(question):
        print("Detected direct factual question - using enhanced query with 'in detail'")
        detailed_query = f"{question} in detail"
        
        # Enhance query with handbook context if available (for better retrieval)
        if handbook_context:
            enhanced_query = f"{detailed_query}\n\nContext from Handbook: {handbook_context[:500]}"
        else:
            enhanced_query = detailed_query
    else:
        # For non-direct questions, use original query
        if handbook_context:
            enhanced_query = f"{question}\n\nContext from Handbook: {handbook_context[:500]}"
        else:
            enhanced_query = question
    
    print(f"Using query for Bare-Law retrieval: {enhanced_query[:100]}...")
    bare_law_docs = bare_law_retriever.invoke(enhanced_query)
    
    # Ensure it's a list
    if not isinstance(bare_law_docs, list):
        bare_law_docs = [bare_law_docs] if bare_law_docs else []
    
    bare_law_context_parts = []
    bare_law_doc_count = len(bare_law_docs)
    ref_counter = 1  # Start reference counter for Bare-Law citations only
    
    if bare_law_docs:
        print(f"Retrieved {bare_law_doc_count} documents from Bare-Law collection")
        
        # Format each document with line-by-line citations and quotes
        for doc in bare_law_docs:
            formatted_content = format_bare_law_citation_with_lines(doc, ref_counter)
            bare_law_context_parts.append(formatted_content)
            ref_counter += 1
        
        bare_law_context = "\n\n---\n\n".join(bare_law_context_parts)
    else:
        bare_law_context = ""
        print("No documents found in Bare-Law collection")
    
    # Step 3: Combine contexts with clear section headers
    context_sections = []
    
    if handbook_context:
        context_sections.append(f"=== Handbook Collection (For Reasoning Only - DO NOT Cite) ===\n{handbook_context}")
    
    if bare_law_context:
        context_sections.append(f"=== Bare-Law Book (For Citations with Page and Line Numbers) ===\n{bare_law_context}")
    
    combined_context = "\n\n".join(context_sections) if context_sections else "No relevant context found."
    
    print(f"Combined context length: {len(combined_context)} characters")
    
    return {
        "context": combined_context,
        "question": question,
        "sources": {
            "Handbook": len(handbook_docs) if handbook_context else 0,
            "Bare-Law": bare_law_doc_count
        }
    }


def build_rag_chain(embedding_client, collection_name=None, force_refresh=False, conversation_history: Optional[List[Tuple[str, str]]] = None, use_smart_assistant: bool = True):
    """
    Builds and returns the LangChain RAG pipeline with smart assistant retrieval:
    1. Checks Handbook collection for relevant context (for reasoning only, NOT for citations)
    2. If useful context found, uses it for understanding the topic
    3. Retrieves line-by-line clauses from Bare-Law collection (for citations only)
    4. Formats Bare-Law with exact page number and line citations with quotes
    5. Includes conversation history for context
    
    Args:
        embedding_client: The embedding client to use
        collection_name: Not used in this implementation (kept for backward compatibility)
        force_refresh: If True, forces a fresh connection to avoid caching (default: False)
        conversation_history: List of (question, answer) tuples from previous conversation turns
        use_smart_assistant: If True, uses smart assistant retrieval with Handbook (reasoning) and Bare-Law (citations) (default: True)
                            If False, uses legacy EY-Papers and Cases retrieval
    """
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0
    )

    if use_smart_assistant:
        # Create retrievers for Handbook and Bare-Law collections
        handbook_retriever = get_retriever(embedding_client, collection_name="Handbook", k=3, force_refresh=force_refresh)
        bare_law_retriever = get_retriever(embedding_client, collection_name="Bare-Law", k=5, force_refresh=force_refresh)
        
        # Create a class to store sources for each invocation
        class SourceTracker:
            def __init__(self):
                self.sources = {"Handbook": 0, "Bare-Law": 0}
            
            def update(self, sources: Dict[str, int]):
                self.sources.update(sources)
            
            def get(self):
                return self.sources.copy()
        
        source_tracker = SourceTracker()
        
        # Format conversation history if provided
        history_text = format_conversation_history(conversation_history or [])
        
        # Create a lambda function that performs smart assistant retrieval
        def retrieve_from_collections(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            result = smart_assistant_retrieval(input_dict, handbook_retriever, bare_law_retriever, llm=llm)
            # Store sources for later retrieval
            source_tracker.update(result.get("sources", {}))
            # Add conversation history to the result
            result["conversation_history"] = history_text
            return result
    else:
        # Legacy mode: EY-Papers and Cases collections
        ey_papers_retriever = get_retriever(embedding_client, collection_name="EY-Papers", force_refresh=force_refresh)
        cases_retriever = get_retriever(embedding_client, collection_name="Cases", force_refresh=force_refresh)
        
        # Create a class to store sources for each invocation
        class SourceTracker:
            def __init__(self):
                self.sources = {"EY-Papers": 0, "Cases": 0}
            
            def update(self, sources: Dict[str, int]):
                self.sources.update(sources)
            
            def get(self):
                return self.sources.copy()
        
        source_tracker = SourceTracker()
        
        # Format conversation history if provided
        history_text = format_conversation_history(conversation_history or [])
        
        # Create a lambda function that performs multi-collection retrieval
        def retrieve_from_collections(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            result = multi_collection_retrieval(input_dict, ey_papers_retriever, cases_retriever, llm=llm)
            # Store sources for later retrieval
            source_tracker.update(result.get("sources", {}))
            # Add conversation history to the result
            result["conversation_history"] = history_text
            return result

    chain = (
        {
            "question": RunnablePassthrough()
        }
        | RunnableLambda(retrieve_from_collections)
        | RAG_PROMPT
        | llm
        | StrOutputParser()
    )
    
    # Attach source tracker to the chain object for access
    chain._source_tracker = source_tracker

    return chain

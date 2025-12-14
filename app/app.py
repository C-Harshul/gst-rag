"""Streamlit frontend for GST RAG system."""

import streamlit as st
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.chain import build_rag_chain
from ingestion.embeddings import cf_embedder
from config.settings import GOOGLE_API_KEY

# Configure Streamlit page
st.set_page_config(
    page_title="GST RAG Assistant",
    page_icon="🇮🇳",
    layout="centered"
)

st.title("GST Assistant")

# Check if required environment variables are set
if not GOOGLE_API_KEY:
    st.error("Please set GOOGLE_API_KEY in your environment variables.")
    st.stop()

# Initialize RAG chain
@st.cache_resource
def initialize_rag_chain():
    """Initialize and cache the RAG chain."""
    try:
        return build_rag_chain(cf_embedder)
    except Exception as e:
        st.error(f"Failed to initialize RAG chain: {str(e)}")
        return None

rag_chain = initialize_rag_chain()

if rag_chain is None:
    st.error("Failed to initialize the system. Please check your configuration.")
    st.stop()

# Chat interface
query = st.text_area(
    "Ask your question:",
    placeholder="Type your question here...",
    height=100
)

if st.button("Send", type="primary"):
    if query and query.strip():
        with st.spinner("Processing..."):
            try:
                response = rag_chain.invoke(query)
                st.markdown(response)
            except Exception as e:
                st.error(f"Error: {str(e)}")
    else:
        st.warning("Please enter a question.")

if __name__ == "__main__":
    pass

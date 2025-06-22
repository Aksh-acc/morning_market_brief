# agents/retrieval_agent/main.py

from fastapi import FastAPI, HTTPException, Query, status
from typing import List, Dict, Any, Optional
import logging

# Import the RAGVectorStore client
from rag.vector_encoding import RAGVectorStore
from langchain_core.documents import Document # For type hinting

# Configure logging for the FastAPI app
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(
    title="Retrieval Agent",
    description="Microservice for retrieving relevant financial information from the vector store.",
    version="1.0.0"
)

# Initialize the RAGVectorStore globally
# This will load the existing Chroma DB from 'chroma_db' or create a new one.
# It's important that the persist_directory matches where you store your embeddings.
try:
    retriever_client = RAGVectorStore(persist_directory="chroma_db")
    logging.info("RAGVectorStore client initialized successfully.")
except Exception as e:
    logging.error(f"Failed to initialize RAGVectorStore: {e}. Retrieval agent may not function correctly.")
    retriever_client = None # Indicate failure

@app.get("/")
async def root():
    """Root endpoint for the Retrieval Agent."""
    return {"message": "Retrieval Agent is running. Use /docs for API documentation."}

@app.post("/retrieve", response_model=List[Dict[str, Any]])
async def retrieve_documents(
    query: str = Query(..., description="The query string to search for in the vector store."),
    k: int = Query(5, ge=1, le=20, description="The number of top relevant documents to retrieve.")
):
    """
    Retrieves the most semantically relevant document chunks from the vector store
    based on a given query.
    """
    if not retriever_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retrieval service not initialized due to underlying error (check logs)."
        )

    if not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty."
        )

    logging.info(f"Received retrieval request for query: '{query}', k={k}")

    # Use the retrieve_relevant_docs method from RAGVectorStore
    retrieved_docs: List[Document] = retriever_client.retrieve_relevant_docs(query, k=k)

    if not retrieved_docs:
        logging.warning(f"No relevant documents found for query: '{query}'")
        return []

    # Convert LangChain Document objects to dictionaries for JSON response
    response_docs = []
    for doc in retrieved_docs:
        response_docs.append({
            "page_content": doc.page_content,
            "metadata": doc.metadata
        })

    logging.info(f"Retrieved {len(response_docs)} documents for query: '{query}'")
    return response_docs
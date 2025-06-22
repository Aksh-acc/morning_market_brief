# rag/vector_store.py

import os
import logging
from typing import List, Dict, Any, Optional

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RAGVectorStore:
    """
    Manages the creation, population, and retrieval from a Chroma vector store
    for Retrieval-Augmented Generation (RAG).
    Handles text chunking, embedding, and similarity search.
    """
    def __init__(self,
                 persist_directory: str = "chroma_db",
                 embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200):
        """
        Initializes the RAGVectorStore.

        Args:
            persist_directory (str): The directory to store the Chroma database.
            embedding_model_name (str): Name of the HuggingFace embedding model to use.
            chunk_size (int): The maximum size of text chunks.
            chunk_overlap (int): The overlap between consecutive text chunks.
        """
        self.persist_directory = persist_directory
        self.embedding_model_name = embedding_model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.embeddings = self._get_embedding_model()
        self.text_splitter = self._get_text_splitter()
        self.vectorstore = self._get_or_create_vectorstore()

        logging.info(f"RAGVectorStore initialized with model '{embedding_model_name}', "
                     f"chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")

    def _get_embedding_model(self) -> HuggingFaceEmbeddings:
        """Initializes and returns the HuggingFace embedding model."""
        try:
            # Ensure a local folder for models if you want to cache them
            model_kwargs = {'device': 'cpu'} # 'cuda' if you have a GPU
            encode_kwargs = {'normalize_embeddings': True} # Recommended for similarity search

            embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_model_name,
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs
            )
            logging.info(f"Loaded embedding model: {self.embedding_model_name}")
            return embeddings
        except Exception as e:
            logging.error(f"Failed to load embedding model {self.embedding_model_name}: {e}")
            raise

    def _get_text_splitter(self) -> RecursiveCharacterTextSplitter:
        """Initializes and returns the text splitter."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )
        logging.info(f"Initialized text splitter with chunk_size={self.chunk_size}, chunk_overlap={self.chunk_overlap}")
        return splitter

    def _get_or_create_vectorstore(self) -> Chroma:
        """
        Gets an existing Chroma vector store or creates a new one if it doesn't exist.
        """
        # Check if the persistence directory exists and has data
        if os.path.exists(self.persist_directory) and len(os.listdir(self.persist_directory)) > 0:
            logging.info(f"Loading existing Chroma DB from {self.persist_directory}")
            return Chroma(persist_directory=self.persist_directory, embedding_function=self.embeddings)
        else:
            logging.info(f"Creating new Chroma DB at {self.persist_directory}")
            # Initialize with no documents; documents will be added via add_documents
            return Chroma(persist_directory=self.persist_directory, embedding_function=self.embeddings)

    def add_documents(self, documents: List[Dict[str, str]]) -> None:
        """
        Adds a list of documents (text and optional metadata) to the vector store.
        Each document dict should have a 'content' key and can optionally have 'metadata'.

        Args:
            documents (List[Dict[str, str]]): A list of dictionaries, where each dict
                                              contains 'content' and optional 'metadata'.
                                              Example: [{'content': '...', 'metadata': {'source': '...'}}]
        """
        if not documents:
            logging.warning("No documents provided to add to the vector store.")
            return

        # Convert input dicts to LangChain Document objects
        langchain_docs = []
        for doc_data in documents:
            content = doc_data.get('content')
            metadata = doc_data.get('metadata', {})
            if content:
                langchain_docs.append(Document(page_content=content, metadata=metadata))
            else:
                logging.warning(f"Skipping document due to missing 'content': {doc_data}")
                
        if not langchain_docs:
            logging.warning("No valid LangChain documents created from input.")
            return

        logging.info(f"Processing {len(langchain_docs)} documents for chunking and embedding...")
        
        # Chunk the documents
        chunks = self.text_splitter.split_documents(langchain_docs)
        logging.info(f"Split documents into {len(chunks)} chunks.")

        if not chunks:
            logging.warning("No chunks generated from documents.")
            return

        try:
            # Add chunks to the vector store
            self.vectorstore.add_documents(chunks)
            # Persist the changes to disk
            self.vectorstore.persist()
            logging.info(f"Successfully added {len(chunks)} chunks to the vector store and persisted changes.")
        except Exception as e:
            logging.error(f"Error adding documents to vector store: {e}")

    def retrieve_relevant_docs(self, query: str, k: int = 5) -> List[Document]:
        """
        Retrieves the most semantically relevant documents (chunks) for a given query.

        Args:
            query (str): The user's query string.
            k (int): The number of top relevant documents to retrieve.

        Returns:
            List[Document]: A list of LangChain Document objects, each containing
                            'page_content' (the chunk text) and 'metadata'.
        """
        if not query:
            logging.warning("Query is empty. Cannot retrieve documents.")
            return []

        try:
            logging.info(f"Retrieving top {k} relevant documents for query: '{query}'")
            # Use similarity_search to find top-k similar chunks
            retrieved_docs = self.vectorstore.similarity_search(query, k=k)
            logging.info(f"Retrieved {len(retrieved_docs)} documents.")
            return retrieved_docs
        except Exception as e:
            logging.error(f"Error retrieving documents for query '{query}': {e}")
            return []

    def clear_vector_store(self) -> None:
        """
        Clears the entire Chroma vector store by deleting its persistence directory.
        Use with caution!
        """
        if os.path.exists(self.persist_directory):
            try:
                import shutil
                shutil.rmtree(self.persist_directory)
                logging.info(f"Chroma DB at {self.persist_directory} cleared successfully.")
                # Re-initialize vectorstore after clearing
                self.vectorstore = self._get_or_create_vectorstore()
            except Exception as e:
                logging.error(f"Error clearing Chroma DB at {self.persist_directory}: {e}")
        else:
            logging.info(f"Chroma DB directory {self.persist_directory} does not exist. Nothing to clear.")

# --- Example Usage ---
if __name__ == "__main__":
    # Ensure the chroma_db directory doesn't exist for a clean start
    if os.path.exists("chroma_db"):
        import shutil
        shutil.rmtree("chroma_db")
        print("Removed existing 'chroma_db' for a clean test.")

    # Initialize the RAGVectorStore
    rag_store = RAGVectorStore(
        persist_directory="chroma_db",
        embedding_model_name="sentence-transformers/all-MiniLM-L6-v2", # Good small model for quick tests
        chunk_size=500,
        chunk_overlap=100
    )

    # --- Sample Data (Simulating data from web scraping or document loading) ---
    sample_documents = [
        {
            "content": "Apple Inc. (AAPL) announced strong Q1 2024 earnings, exceeding analyst expectations "
                       "with iPhone sales leading the growth. Services revenue also showed significant "
                       "improvement, driven by App Store and Apple Music subscriptions. The company "
                       "projects continued growth in the upcoming quarter, despite macroeconomic headwinds.",
            "metadata": {"source": "TechNews.com", "date": "2024-02-01"}
        },
        {
            "content": "In its latest earnings report, Tesla (TSLA) reported lower-than-expected vehicle deliveries "
                       "for Q1 2024, impacting its stock price. Elon Musk commented on production challenges "
                       "and the competitive EV market. The company emphasized its focus on AI and robotics "
                       "development as future growth drivers.",
            "metadata": {"source": "AutoDaily.net", "date": "2024-04-25"}
        },
        {
            "content": "Microsoft (MSFT) unveiled new AI-powered features for its Azure cloud platform, "
                       "aiming to enhance enterprise solutions. The partnership with OpenAI continues to "
                       "yield innovative products, attracting more corporate clients to its AI services. "
                       "Analysts remain bullish on MSFT's cloud computing division.",
            "metadata": {"source": "BusinessTechNews.com", "date": "2024-05-15"}
        },
        {
            "content": "The Federal Reserve indicated that inflation remains a concern, suggesting that "
                       "interest rate cuts might be delayed. This news led to a sell-off in growth stocks "
                       "and a cautious sentiment across the broader market. Investors are advised to "
                       "monitor upcoming CPI data closely.",
            "metadata": {"source": "FinancialTimes.com", "date": "2024-05-28"}
        },
        {
            "content": "Google's parent company Alphabet (GOOGL) announced a significant investment in "
                       "quantum computing research, signaling its long-term commitment to advanced technologies. "
                       "This comes amidst growing competition in the AI sector and a push for more efficient "
                       "data processing solutions.",
            "metadata": {"source": "TechCrunch.com", "date": "2024-05-20"}
        },
        {
            "content": "A new report by a leading financial analyst firm suggests that renewable energy "
                       "stocks are poised for a significant rally in the second half of 2024, driven by "
                       "government incentives and decreasing production costs. Companies like First Solar "
                       "and NextEra Energy are highlighted.",
            "metadata": {"source": "AnalystReport.pdf", "date": "2024-05-27"}
        }
    ]

    # --- Add documents to the vector store ---
    print("\n--- Adding documents to the vector store ---")
    rag_store.add_documents(sample_documents)

    # --- Test retrieval ---
    print("\n--- Testing document retrieval ---")

    queries = [
        "What are the latest developments in AI and cloud computing?",
        "Tell me about Apple's recent earnings.",
        "What's happening with interest rates?",
        "Any news on Tesla's deliveries?",
        "Insights on renewable energy stocks?"
    ]

    for query in queries:
        print(f"\nQuery: '{query}'")
        retrieved_docs = rag_store.retrieve_relevant_docs(query, k=2) # Get top 2 results

        if retrieved_docs:
            for i, doc in enumerate(retrieved_docs):
                print(f"  Result {i+1} (Source: {doc.metadata.get('source', 'N/A')}):")
                print(f"    {doc.page_content[:200]}...") # Print first 200 chars of chunk
        else:
            print("  No relevant documents found.")

    # --- Test reloading from persistence (optional) ---
    print("\n--- Testing persistence (reloading the store) ---")
    del rag_store # Delete the current instance
    reloaded_rag_store = RAGVectorStore(persist_directory="chroma_db")
    reloaded_docs = reloaded_rag_store.retrieve_relevant_docs("Apple earnings", k=1)
    if reloaded_docs:
        print(f"\nReloaded store query 'Apple earnings': {reloaded_docs[0].page_content[:100]}...")
    else:
        print("\nReloaded store failed to retrieve documents.")

    # --- Clear the vector store (optional, for clean runs) ---
    # print("\n--- Clearing the vector store ---")
    # rag_store.clear_vector_store()
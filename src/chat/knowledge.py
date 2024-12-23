# knowledge.py

import logging

from phi.vectordb.pgvector import PgVector

from utils.llm_helper import get_embedder
from .custom_knowledge_base import CustomKnowledgeBase
from config import POSTGRES_CONNECTION

# Setup logging
logger = logging.getLogger(__name__)

# Initialize a unified PgVector for all documents

try:
    embedder = get_embedder()
    logger.info(f"Initialized OpenAI embedder: {embedder}")
    
    # Test embedding creation
    test_text = "Schoolio test embedding"
    logger.info("Creating test embedding...")
    
    # Use get_embedding instead of encode
    test_embedding = embedder.get_embedding(test_text)
    embedding_dim = len(test_embedding)
    logger.info(f"Test embedding successful - dimensions: {embedding_dim}")
    
    if embedding_dim != 1536:
        logger.error(f"OpenAI embedding dimension mismatch! Got {embedding_dim}, expected 1536")
        raise ValueError(f"OpenAI embedding dimension mismatch: {embedding_dim} vs 1536")

except Exception as e:
    logger.error(f"Embedder initialization/test failed: {str(e)}")
    raise


# Initialize PgVector with explicit error handling
try:
    vector_db = PgVector(
        table_name="documents",
        db_url=POSTGRES_CONNECTION,
        embedder=embedder
    )
    logger.info(f"Vector DB initialized successfully with table: {vector_db.table_name}")
    
    # Test vector search functionality
    test_results = vector_db.search(
        query="test query",
        limit=1
    )
    logger.info(f"Vector search test {'successful' if test_results is not None else 'failed'}")
    
except Exception as e:
    logger.error(f"Vector DB initialization/test failed: {str(e)}")
    raise

# Initialize knowledge base
knowledge_base = CustomKnowledgeBase(
    sources=[],
    vector_db=vector_db,
)
logger.info("Knowledge base initialized successfully")
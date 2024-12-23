# knowledge.py

import logging

from phi.vectordb.pgvector import PgVector

from utils.llm_helper import get_embedder
from .custom_knowledge_base import CustomKnowledgeBase
from config import POSTGRES_CONNECTION

# Setup logging
logger = logging.getLogger(__name__)

# Initialize a unified PgVector for all documents
vector_db = PgVector(
    table_name="documents",  # Unified table
    db_url=POSTGRES_CONNECTION,
    embedder=get_embedder(),
    schema_name="ai"  # Add this line
)

# Initialize CustomKnowledgeBase
knowledge_base = CustomKnowledgeBase(
    sources=[
        # Add other knowledge sources here if needed
    ],
    vector_db=vector_db,
)

logger.info("Knowledge base initialized with vector DB.")

# knowledge.py

from phi.vectordb.pgvector import PgVector
from utils.llm_helper import get_embedder

from .custom_knowledge_base import CustomKnowledgeBase
from config import POSTGRES_CONNECTION

# Initialize a unified PgVector for all documents
vector_db = PgVector(
    table_name="documents",  # Unified table
    db_url=POSTGRES_CONNECTION,
    embedder=get_embedder(),
)

# Initialize CustomKnowledgeBase
knowledge_base = CustomKnowledgeBase(
    sources=[
        # Add other knowledge sources here if needed
    ],
    vector_db=vector_db,
)

# knowledge.py

from typing import List, Any
from phi.vectordb.pgvector import PgVector
from config import POSTGRES_CONNECTION
from utils.llm_helper import get_embedder
from utils.url_helper import is_valid_url, normalize_url
from phi.utils.log import logger

from .custom_knowledge_base import CustomKnowledgeBase

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

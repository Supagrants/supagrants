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

# Function to initialize all vector databases
async def initialize_knowledge_base():
    await vector_db.initialize()

async def handle_document(file_info: dict):
    mime_type = file_info.get('mime_type')
    if mime_type == 'application/pdf':
        await knowledge_base.handle_pdf_file(file_info)
    elif mime_type == 'text/plain':
        await knowledge_base.handle_txt_file(file_info)
    else:
        logger.warning(f"Unsupported MIME type: {mime_type}")
    return

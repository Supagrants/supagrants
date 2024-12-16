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

async def handle_url(url: str, crawled_content: Any):
    if not is_valid_url(url):
        logger.warning(f"Invalid URL format: {url}")
        return

    try:
        if await knowledge_base.is_source_indexed(url):
            logger.info(f"Duplicate URL detected, skipping: {url}")
            return

        # Ensure crawled_content is a string
        if isinstance(crawled_content, list):
            crawled_content = ' '.join(crawled_content)
            logger.debug(f"Joined crawled_content into string: {crawled_content}")

        if not isinstance(crawled_content, str):
            logger.error(f"crawled_content is not a string for URL {url}.")
            return

        metadata = await knowledge_base.extract_metadata(url, crawled_content)
        document = {
            "title": metadata.get("title", url),
            "content": crawled_content,
            "meta_data": metadata
        }
        await knowledge_base.add_document(document, document_type="url")
        logger.info(f"Indexed URL in pgvector: {url}")
    except Exception as e:
        logger.error(f"Error indexing URL {url}: {e}")
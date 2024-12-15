# knowledge.py

from typing import List, Any
from phi.knowledge.pdf import PDFUrlKnowledgeBase
from phi.vectordb.pgvector import PgVector
from config import POSTGRES_CONNECTION
from utils.llm_helper import get_embedder
from utils.url_helper import is_valid_url
from phi.utils.log import logger

from .custom_knowledge_base import CustomKnowledgeBase  # Import the new class

# Initialize a unified PgVector for all documents
vector_db = PgVector(
    table_name="documents",  # Unified table
    db_url=POSTGRES_CONNECTION,
    embedder=get_embedder(),
)

# Initialize PDF knowledge base with document_type
pdf_knowledge_base = PDFUrlKnowledgeBase(
    urls=[],
    vector_db=vector_db,
    document_type="pdf"
)

# Initialize CustomKnowledgeBase
knowledge_base = CustomKnowledgeBase(
    sources=[
        pdf_knowledge_base,
        # Add other knowledge sources here if needed
    ],
    vector_db=vector_db,
)

# Function to initialize all vector databases
async def initialize_knowledge_base():
    await vector_db.initialize()

async def handle_document(file_info: dict):
    if file_info['mime_type'] == 'application/pdf':
        pdf_knowledge_base.urls = [file_info['file_url']]
        await pdf_knowledge_base.load(recreate=False)  # Ensure this is awaited
    return

async def handle_url(url: str, crawled_content: Any):
    if not is_valid_url(url):
        logger.warning(f"Invalid URL format: {url}")
        return

    try:
        if await knowledge_base.is_duplicate(url):
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

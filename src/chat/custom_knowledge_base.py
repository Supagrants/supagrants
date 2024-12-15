# custom_knowledge_base.py

from typing import List, Optional, Iterator, Dict, Any
import json
import asyncio

from pydantic import BaseModel
from phi.document import Document
from phi.knowledge.agent import AgentKnowledge
from phi.vectordb.pgvector import PgVector
from phi.utils.log import logger
from bs4 import BeautifulSoup

from utils.llm_helper import get_embedder
from utils.validation import is_valid_url
from sqlalchemy import text

class CustomKnowledgeBase(AgentKnowledge):
    """
    Custom Knowledge Base that extends CombinedKnowledgeBase to include dynamic document addition.
    """

    def __init__(self, sources: List[AgentKnowledge], vector_db: PgVector):
        super().__init__(sources=sources, vector_db=vector_db)

    @property
    def document_lists(self) -> Iterator[List[Document]]:
        """Iterate over knowledge bases and yield lists of documents."""
        for kb in self.sources:
            logger.debug(f"Loading documents from {kb.__class__.__name__}")
            yield from kb.document_lists

    async def add_document(self, document: Dict[str, Any], document_type: Optional[str] = None):
        """
        Asynchronously add a document to the CombinedKnowledgeBase.

        Args:
            document (Dict[str, Any]): The document to add, containing 'title', 'content', and 'meta_data'.
            document_type (Optional[str]): The type/source of the document (e.g., 'pdf', 'url').
        """
        try:
            title = document.get("title", "")
            content = document.get("content", "")
            meta_data = document.get("meta_data", {})  # Changed from 'metadata' to 'meta_data'
            if document_type:
                meta_data['document_type'] = document_type

            # Create a Document instance
            doc = Document(
                id=None,  # Let PgVector handle ID generation if applicable
                name=title,
                content=content,
                meta_data=meta_data,
                embedder=self.vector_db.embedder  # Ensure embedder is set
            )

            # Run the synchronous insert method in an executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.vector_db.insert, [doc])

            logger.info(f"Indexed document in pgvector: {title}")

        except Exception as e:
            logger.error(f"Error indexing document '{document.get('title', '')}': {e}")
            raise e

    async def handle_url(self, url: str, crawled_content: Any):
        """
        Handle crawled URLs by adding their content to the CombinedKnowledgeBase in PostgreSQL.

        Args:
            url (str): The URL that was crawled.
            crawled_content (Any): The content retrieved from crawling the URL.
        """
        if not is_valid_url(url):
            logger.warning(f"Invalid URL format: {url}")
            return

        try:
            if await self.is_duplicate(url):
                logger.info(f"Duplicate URL detected, skipping: {url}")
                return

            # Ensure crawled_content is a string
            if isinstance(crawled_content, list):
                crawled_content = ' '.join(crawled_content)
                logger.debug(f"Joined crawled_content into string: {crawled_content}")

            if not isinstance(crawled_content, str):
                logger.error(f"crawled_content is not a string for URL {url}.")
                return

            metadata = await self.extract_metadata(url, crawled_content)
            document = {
                "title": metadata.get("title", url),
                "content": crawled_content,
                "meta_data": metadata  # Changed from 'metadata' to 'meta_data'
            }
            await self.add_document(document, document_type="url")
            logger.info(f"Indexed URL in pgvector: {url}")
        except Exception as e:
            logger.error(f"Error indexing URL {url}: {e}")

    async def extract_metadata(self, url: str, content: str) -> Dict[str, Any]:
        """
        Extract metadata from the crawled content.

        Args:
            url (str): The URL of the project.
            content (str): The HTML content retrieved from the URL.

        Returns:
            Dict[str, Any]: Extracted metadata.
        """
        metadata = {}
        try:
            soup = BeautifulSoup(content, 'html.parser')
            title = soup.title.string.strip() if soup.title and soup.title.string else url
            description_tag = soup.find('meta', attrs={'name': 'description'})
            description = description_tag['content'].strip() if description_tag and description_tag.get('content') else ''

            # Extract additional metadata as needed
            og_description = soup.find('meta', property='og:description')
            if og_description and og_description.get('content'):
                metadata['og_description'] = og_description['content'].strip()

            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                metadata['og_image'] = og_image['content'].strip()

            # Add other metadata fields here as needed

            metadata = {
                "source": url,
                "title": title,
                "description": description,
                "og_description": metadata.get('og_description', ''),
                "og_image": metadata.get('og_image', ''),
                # Add other metadata fields here
            }
        except Exception as e:
            logger.error(f"Error extracting metadata from {url}: {e}")

        return metadata

    async def is_duplicate(self, url: str) -> bool:
        """
        Check if a URL is already indexed.

        Args:
            url (str): The URL to check.

        Returns:
            bool: True if duplicate, False otherwise.
        """
        query = f"SELECT EXISTS(SELECT 1 FROM {self.vector_db.table_name} WHERE meta_data->>'source' = :url)"
        try:
            loop = asyncio.get_event_loop()
            exists = await loop.run_in_executor(
                None,
                self._execute_exists_query,
                query,
                url
            )
            return exists
        except Exception as e:
            logger.error(f"Error checking duplicate for URL {url}: {e}")
            return False

    def _execute_exists_query(self, query: str, url: str) -> bool:
        """
        Execute the duplicate check query synchronously.

        Args:
            query (str): The SQL query to execute.
            url (str): The URL parameter for the query.

        Returns:
            bool: Result of the duplicate check.
        """
        try:
            with self.vector_db.Session() as sess, sess.begin():
                result = sess.execute(text(query), {"url": url}).scalar()
                return result if result is not None else False
        except Exception as e:
            logger.error(f"Error executing duplicate check query: {e}")
            return False

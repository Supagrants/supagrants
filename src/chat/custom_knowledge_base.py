# custom_knowledge_base.py

import logging
from typing import List, Optional, Iterator, Dict, Any
import json
import asyncio
from hashlib import md5
import uuid
import re

from pydantic import BaseModel
from phi.document import Document
from phi.knowledge.agent import AgentKnowledge
from phi.vectordb.pgvector import PgVector
from phi.utils.log import logger
from bs4 import BeautifulSoup

from utils.llm_helper import get_embedder
from utils.validation import is_valid_url
from sqlalchemy import text

# Define MAX_CHUNK_SIZE at the module level
MAX_CHUNK_SIZE = 9000  # bytes

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

    def split_content_into_chunks(self, content: str, max_size: int) -> List[str]:
        # Semantic chunking based on sentences
        sentences = re.split(r'(?<=[.!?]) +', content)
        chunks = []
        current_chunk = ""
        for sentence in sentences:
            # Encode to bytes to accurately measure size
            sentence_size = len(sentence.encode('utf-8'))
            current_size = len(current_chunk.encode('utf-8'))
            if current_size + sentence_size + 1 <= max_size:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # Start new chunk with the current sentence
                if sentence_size <= max_size:
                    current_chunk = sentence
                else:
                    # If single sentence exceeds max_size, split it
                    split_sentences = [sentence[i:i+max_size] for i in range(0, len(sentence), max_size)]
                    chunks.extend(split_sentences[:-1])
                    current_chunk = split_sentences[-1]
        if current_chunk:
            chunks.append(current_chunk)
        logger.info(f"Total chunks created: {len(chunks)}")
        return chunks

    def compute_content_hash(self, content: str) -> str:
        """
        Compute the MD5 hash of the content.

        Args:
            content (str): The content to hash.

        Returns:
            str: The MD5 hash of the content.
        """
        cleaned_content = self._clean_content(content)
        return md5(cleaned_content.encode()).hexdigest()

    def _clean_content(self, content: str) -> str:
        """
        Clean the content by replacing null characters.

        Args:
            content (str): The content to clean.

        Returns:
            str: The cleaned content.
        """
        return content.replace("\x00", "\ufffd")

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
            meta_data = document.get("meta_data", {})
            if document_type:
                meta_data['document_type'] = document_type

            # Split content into chunks using the module-level MAX_CHUNK_SIZE
            chunks = self.split_content_into_chunks(content, MAX_CHUNK_SIZE)
            if not chunks:
                logger.error("No chunks were created from the content. Aborting insertion.")
                return

            # Create Document instances for each chunk
            docs = []
            base_content_hash = self.compute_content_hash(content)
            for idx, chunk in enumerate(chunks):
                chunk_id = f"{base_content_hash}_chunk_{idx}"  # Unique ID based on content hash and chunk index
                chunk_meta_data = meta_data.copy()
                chunk_meta_data['chunk'] = idx + 1
                chunk_meta_data['total_chunks'] = len(chunks)
                chunk_meta_data['usage'] = {
                    "last_accessed": None,
                    "access_count": 0
                }  # Initialize usage data as needed

                logger.debug(f"Generating embedding for chunk {idx} of document '{title}' with id '{chunk_id}'.")

                # Manually generate embedding with retry logic
                try:
                    embedder = self.vector_db.embedder
                    embedding = await self.get_embedding_with_retries(embedder, chunk)
                    if not embedding:
                        logger.error(f"Embedding not generated for chunk {idx} of document '{title}'. Skipping.")
                        continue
                    if len(embedding) != self.vector_db.dimensions:
                        logger.error(f"Embedding dimension mismatch for chunk {idx} of document '{title}'. Expected {self.vector_db.dimensions}, got {len(embedding)}. Skipping.")
                        continue
                except Exception as e:
                    logger.error(f"Exception during embedding generation for chunk {idx} of document '{title}': {e}. Skipping.")
                    continue

                # Create Document instance with the generated embedding
                doc = Document(
                    id=chunk_id,
                    name=title,
                    content=chunk,
                    meta_data=chunk_meta_data,
                    embedding=embedding  # Assign the generated embedding directly
                )

                docs.append(doc)

            if not docs:
                logger.error("No valid document chunks to insert after embedding generation.")
                return

            # Run the synchronous insert method in an executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.vector_db.insert, docs)

            logger.info(f"Indexed {len(docs)} chunks of document in pgvector: {title}")

        except Exception as e:
            logger.error(f"Error indexing document '{document.get('title', '')}': {e}")
            raise e

    async def get_embedding_with_retries(self, embedder, text, retries=3, delay=2):
        """
        Generate embeddings with retry logic.

        Args:
            embedder: The embedder instance.
            text (str): The text to embed.
            retries (int): Number of retry attempts.
            delay (int): Initial delay between retries.

        Returns:
            List[float]: The generated embedding or None if failed.
        """
        for attempt in range(1, retries + 1):
            try:
                embedding = embedder.get_embedding(text)
                if embedding:
                    logger.debug(f"Embedding generated successfully on attempt {attempt}.")
                    return embedding
                else:
                    logger.warning(f"Attempt {attempt}: Embedding returned None.")
            except Exception as e:
                logger.warning(f"Attempt {attempt} failed for embedding generation: {e}")
            if attempt < retries:
                logger.info(f"Retrying embedding generation after {delay} seconds...")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
        logger.error(f"All {retries} attempts failed for embedding generation.")
        return None

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
                "meta_data": metadata
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

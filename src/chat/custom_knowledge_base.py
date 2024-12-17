# custom_knowledge_base.py

import logging
from typing import List, Optional, Iterator, Dict, Any
import json
import asyncio
from hashlib import md5
import re
import io

from pydantic import BaseModel
from phi.document import Document
from phi.knowledge.agent import AgentKnowledge
from phi.vectordb.pgvector import PgVector
from bs4 import BeautifulSoup
import aiohttp
from sqlalchemy import text
from pdfminer.high_level import extract_text

from utils.llm_helper import get_embedder
from utils.url_helper import is_valid_url, normalize_url

MAX_CHUNK_SIZE = 9000  # bytes

# Setup logging
logger = logging.getLogger(__name__)

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
        logger.debug(f"Total chunks created: {len(chunks)}")
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
            document_type (Optional[str]): The type/source of the document (e.g., 'pdf', 'url', 'txt').
        """
        try:
            title = document.get("title", "")
            content = document.get("content", "")
            meta_data = document.get("meta_data", {})
            if document_type:
                meta_data['document_type'] = document_type  # Optional: Retain in meta_data if needed

            # Initialize 'filters' in meta_data if not present
            if 'filters' not in meta_data:
                meta_data['filters'] = {}

            # Split content into chunks using the module-level MAX_CHUNK_SIZE
            chunks = self.split_content_into_chunks(content, MAX_CHUNK_SIZE)
            if not chunks:
                logger.error("No chunks were created from the content. Aborting insertion.")
                return

            # Create Document instances for each chunk
            docs = []
            source_hash = self.compute_content_hash(meta_data.get("source", ""))
            content_hash = self.compute_content_hash(content)
            for idx, chunk in enumerate(chunks):
                chunk_id = f"{source_hash}_{content_hash}_chunk_{idx}"  # Unique ID based on source_hash, content hash and chunk index
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

            # Prepare SQL statement with ON CONFLICT clause, including 'document_type'
            insert_query = f"""
            INSERT INTO {self.vector_db.schema}.{self.vector_db.table_name} (
                id, name, meta_data, filters, content, embedding, usage, content_hash, document_type
            )
            VALUES (
                :id, :name, :meta_data, :filters, :content, :embedding, :usage, :content_hash, :document_type
            )
            ON CONFLICT (id) 
            DO UPDATE SET 
                name = EXCLUDED.name,
                meta_data = EXCLUDED.meta_data,
                filters = EXCLUDED.filters,
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                usage = EXCLUDED.usage,
                content_hash = EXCLUDED.content_hash,
                document_type = EXCLUDED.document_type;
            """

            # Insert documents using a synchronous helper function
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._insert_documents_sync, insert_query, docs, document_type)

            logger.debug(f"Indexed {len(docs)} chunks of document in pgvector: {title}")

        except Exception as e:
            logger.error(f"Error indexing document '{document.get('title', '')}': {e}")
            raise e

    def _insert_documents_sync(self, insert_query: str, docs: List[Document], document_type: str):
        """
        Synchronously insert documents into the database.

        Args:
            insert_query (str): The SQL insert query with ON CONFLICT clause.
            docs (List[Document]): The list of Document instances to insert.
            document_type (str): The type of the document being inserted.
        """
        try:
            with self.vector_db.Session() as sess:
                with sess.begin():
                    overall_result = None
                    for doc in docs:
                        try:
                            filters = doc.meta_data.get('filters', {})
                            result = sess.execute(
                                text(insert_query),
                                {
                                    "id": doc.id,
                                    "name": doc.name,
                                    "meta_data": json.dumps(doc.meta_data),
                                    "filters": json.dumps(filters) if filters else '{}',
                                    "content": doc.content,
                                    "embedding": json.dumps(doc.embedding),
                                    "usage": json.dumps(doc.meta_data.get('usage', {})),
                                    "content_hash": self.compute_content_hash(doc.content),
                                    "document_type": document_type
                                }
                            )
                            
                            # Keep track of the last insert result, or aggregate results
                            overall_result = result

                            if result.rowcount > 0:
                                logger.info(f"Successfully inserted document with ID: {doc.id}")
                            else:
                                logger.warning(f"No rows affected for document ID: {doc.id}")
                            
                        except Exception as e:
                            logger.error(f"Error inserting document ID {doc.id}: {e}")
                            continue

                    return overall_result  # Or return something meaningful after the loop
        except Exception as e:
            logger.error(f"Error during document insertion: {e}")

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
            # Normalize the URL
            normalized_url = normalize_url(url)
            logger.debug(f"Normalized URL for handling: {normalized_url}")

            # Ensure crawled_content is a string
            if isinstance(crawled_content, list):
                crawled_content = ' '.join(crawled_content)
                logger.debug(f"Joined crawled_content into string: {crawled_content}")

            if not isinstance(crawled_content, str):
                logger.error(f"crawled_content is not a string for URL {url}.")
                return

            metadata = await self.extract_metadata(normalized_url, crawled_content)
            document = {
                "title": metadata.get("title", normalized_url),
                "content": crawled_content,
                "meta_data": metadata
            }
            await self.add_document(document, document_type="url")
            logger.info(f"Indexed URL in pgvector: {normalized_url}")
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

    async def is_source_indexed(self, source: str) -> bool:
        """
        Check if a source is already indexed.

        Args:
            source (str): The source URL or file path.

        Returns:
            bool: True if the source is already indexed, False otherwise.
        """
        query = f"SELECT EXISTS(SELECT 1 FROM {self.vector_db.schema}.{self.vector_db.table_name} WHERE meta_data->>'source' = :source)"
        
        logger.debug(f"Checking if source is indexed: {source}")

        try:
            loop = asyncio.get_event_loop()
            exists = await loop.run_in_executor(
                None,
                self._execute_exists_query,
                query,
                source
            )
            logger.debug(f"Duplicate source check result for '{source}': {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking duplicate source for '{source}': {e}")
            return False

    def _execute_exists_query(self, query: str, source: str) -> bool:
        """
        Execute the duplicate check query synchronously.

        Args:
            query (str): The SQL query to execute.
            source (str): The source parameter for the query.

        Returns:
            bool: Result of the duplicate check.
        """
        try:
            with self.vector_db.Session() as sess, sess.begin():
                result = sess.execute(text(query), {"source": source}).scalar()
                logger.debug(f"Query Result for source '{source}': {result}")
                return result if result is not None else False
        except Exception as e:
            logger.error(f"Error executing duplicate source check for '{source}': {e}")
            return False

    async def handle_txt_file(self, file_info: dict):
        """
        Handle TXT files by downloading and indexing their content.

        Args:
            file_info (dict): Information about the TXT file, including 'file_url', 'file_name', etc.
        """
        if file_info.get('mime_type') != 'text/plain':
            logger.warning(f"Unsupported MIME type for TXT handling: {file_info.get('mime_type')}")
            return

        source = file_info['file_url']
        if await self.is_source_indexed(source):
            logger.info(f"Duplicate source detected, skipping: {source}")
            return

        try:
            file_content_bytes = await self.download_file(file_info['file_url'])
            if not file_content_bytes:
                logger.error(f"Failed to download TXT file: {file_info['file_url']}")
                return

            # Decode bytes to string
            try:
                file_content = file_content_bytes.decode('utf-8')  # Adjust encoding if necessary
            except UnicodeDecodeError as e:
                logger.error(f"Failed to decode TXT file content from {file_info['file_url']}: {e}")
                return

            # Generate content hash
            content_hash = self.compute_content_hash(file_content)

            # Prepare metadata
            metadata = {
                "source": file_info['file_url'],
                "original_filename": file_info['file_name'],
                "document_type": "txt",
                # Add other metadata fields as needed
            }

            # Create document dictionary
            document = {
                "title": file_info['file_name'],
                "content": file_content,
                "meta_data": metadata
            }

            # Add document with 'txt' as document_type
            await self.add_document(document, document_type="txt")
            logger.info(f"Indexed TXT file: {file_info['file_name']}")

        except Exception as e:
            logger.error(f"Error indexing TXT file {file_info.get('file_name', '')}: {e}")

    async def handle_pdf_file(self, file_info: dict):
        """
        Handle PDF files by downloading, extracting text, and indexing their content.

        Args:
            file_info (dict): Information about the PDF file, including 'file_url', 'file_name', etc.
        """
        if file_info.get('mime_type') != 'application/pdf':
            logger.warning(f"Unsupported MIME type for PDF handling: {file_info.get('mime_type')}")
            return

        source = file_info['file_url']
        if await self.is_source_indexed(source):
            logger.info(f"Duplicate source detected, skipping: {source}")
            return

        try:
            file_content = await self.download_file(file_info['file_url'])
            if not file_content:
                logger.error(f"Failed to download PDF file: {file_info['file_url']}")
                return

            # Extract text from PDF
            extracted_text = await self.extract_text_from_pdf(file_content)
            if not extracted_text:
                logger.error(f"No text extracted from PDF file: {file_info['file_url']}")
                return

            # Generate content hash
            content_hash = self.compute_content_hash(extracted_text)

            # Prepare metadata
            metadata = {
                "source": file_info['file_url'],
                "original_filename": file_info['file_name'],
                "document_type": "pdf",
                # Add other metadata fields as needed
            }

            # Create document dictionary
            document = {
                "title": file_info['file_name'],
                "content": extracted_text,
                "meta_data": metadata
            }

            # Add document with 'pdf' as document_type
            await self.add_document(document, document_type="pdf")
            logger.info(f"Indexed PDF file: {file_info['file_name']}")

        except Exception as e:
            logger.error(f"Error indexing PDF file {file_info.get('file_name', '')}: {e}")

    async def extract_text_from_pdf(self, pdf_bytes: bytes) -> Optional[str]:
        """
        Extract text from a PDF file.

        Args:
            pdf_bytes (bytes): The raw bytes of the PDF file.

        Returns:
            Optional[str]: The extracted text or None if extraction fails.
        """
        try:
            with io.BytesIO(pdf_bytes) as pdf_file:
                text = extract_text(pdf_file)
                logger.debug("Extracted text from PDF successfully.")
                return text
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            return None

    async def download_file(self, file_url: str) -> Optional[bytes]:
        """
        Download the content of a file from a given URL.

        Args:
            file_url (str): The URL of the file to download.

        Returns:
            Optional[bytes]: The content of the file as bytes, or None if failed.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.error(f"Failed to download file. Status code: {response.status} for URL: {file_url}")
                        return None
        except Exception as e:
            logger.error(f"Exception during file download from {file_url}: {e}")
            return None

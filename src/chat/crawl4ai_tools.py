# crawl4ai_tools.py

import asyncio
from typing import Optional, Set, AsyncGenerator, Tuple, Callable
from urllib.parse import urljoin, urlparse, urldefrag
import re
import logging

from phi.tools import Toolkit
from markdown import markdown
from bs4 import BeautifulSoup

try:
    from crawl4ai import AsyncWebCrawler, CacheMode
except ImportError:
    raise ImportError("crawl4ai not installed. Please install using pip install crawl4ai")

from utils.url_helper import is_valid_url, normalize_url

logger = logging.getLogger(__name__)


class Crawl4aiTools(Toolkit):
    def __init__(
        self,
        max_length: Optional[int] = 1000,
        max_depth: int = 2,
        max_pages: int = 50,
        max_concurrent_tasks: int = 4,
    ):
        """
        Initializes the Crawl4aiTools with options for recursive crawling.

        :param max_length: The maximum length of the result per page.
        :param max_depth: The maximum depth for recursive crawling.
        :param max_pages: The maximum number of pages to crawl.
        :param max_concurrent_tasks: The maximum number of concurrent crawling tasks.
        """
        super().__init__(name="crawl4ai_tools")

        self.max_length = max_length
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.max_concurrent_tasks = max_concurrent_tasks

        self.register(self.web_crawler)

    async def web_crawler(
        self,
        start_url: str,
        is_duplicate: Callable[[str], asyncio.Future],
        on_page_crawled: Callable[[str, str], asyncio.Future],
        max_length: Optional[int] = None,
        max_depth: Optional[int] = None,
        max_pages: Optional[int] = None,
    ) -> AsyncGenerator[Tuple[str, str], None]:
        """
        Asynchronous generator to recursively crawl a website using AsyncWebCrawler.
        Utilizes external callbacks to handle duplication checks and post-crawl actions.

        :param start_url: The URL to start crawling from.
        :param is_duplicate: Async function to check if a URL is already indexed.
        :param on_page_crawled: Async function to handle the crawled page.
        :param max_length: The maximum length of the result per page.
        :param max_depth: The maximum depth for recursion.
        :param max_pages: The maximum number of pages to crawl.

        :yield: Tuples containing (URL, page content) as strings.
        """
        if not start_url:
            yield ("No URL provided", "")
            return

        max_length = max_length or self.max_length
        max_depth = max_depth or self.max_depth
        max_pages = max_pages or self.max_pages

        crawled_urls: Set[str] = set()
        pages_crawled = 0

        semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        async with AsyncWebCrawler(thread_safe=True) as crawler:

            async def crawl(url: str, depth: int) -> AsyncGenerator[Tuple[str, str], None]:
                nonlocal pages_crawled
                if depth > max_depth or pages_crawled >= max_pages:
                    return

                normalized_url = normalize_url(url)

                # Prevent crawling already visited or indexed URLs
                if normalized_url in crawled_urls:
                    logger.debug(f"URL already crawled or indexed: {normalized_url}")
                    return

                # Acquire semaphore before proceeding
                await semaphore.acquire()
                try:
                    # Check if the URL is already indexed using the callback
                    is_dup = await is_duplicate(normalized_url)
                    crawled_urls.add(normalized_url)  # Mark as crawled regardless of duplication

                    if not is_dup:
                        pages_crawled += 1

                    try:
                        result = await crawler.arun(url=url, cache_mode=CacheMode.BYPASS)
                    except Exception as e:
                        error_msg = f"Error crawling {url}: {e}"
                        logger.error(error_msg)
                        yield (url, error_msg)
                        return

                    if result and result.markdown:
                        # Normalize whitespace: replace multiple whitespace with single space and strip
                        content = re.sub(r'\s+', ' ', result.markdown).strip()
                        # Truncate content gracefully
                        if max_length:
                            content = self.truncate_content(content, max_length)

                        if not is_dup:
                            yield (normalized_url, content)
                            # Handle the crawled page using the callback
                            await on_page_crawled(normalized_url, content)

                        # Extract links for further crawling
                        links = self._extract_links(result.markdown, normalized_url)
                        for link in links:
                            if is_valid_url(link):
                                async for page in crawl(link, depth + 1):
                                    yield page
                finally:
                    # Release semaphore after crawling
                    semaphore.release()

            # Start crawling from the start_url
            async for page in crawl(start_url, depth=1):
                yield page

    def _extract_links(self, markdown_text: str, base_url: str) -> Set[str]:
        """
        Extracts and normalizes URLs from markdown content.

        :param markdown_text: The markdown content to extract links from.
        :param base_url: The base URL to resolve relative links.

        :return: A set of normalized extracted URLs.
        """
        # Convert markdown to HTML
        html = markdown(markdown_text)
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # Remove URL fragments
            href, _ = urldefrag(href)
            parsed_href = urlparse(href)
            if parsed_href.scheme in ('http', 'https', ''):
                # Resolve relative URLs
                full_url = urljoin(base_url, href)
                # Normalize URL by removing fragments and lowercasing the scheme and hostname
                normalized_full_url = normalize_url(full_url)
                links.add(normalized_full_url)
        logger.debug(f"Extracted {len(links)} links from base URL: {base_url}")
        return links

    def truncate_content(self, content: str, max_length: int) -> str:
        """
        Truncates the content to the nearest space before max_length to avoid cutting words.

        :param content: The content to truncate.
        :param max_length: The maximum allowed length.

        :return: The truncated content.
        """
        if len(content) <= max_length:
            return content
        # Find the last space before max_length
        trunc_point = content.rfind(' ', 0, max_length)
        if trunc_point == -1:
            return content[:max_length]
        return content[:trunc_point]

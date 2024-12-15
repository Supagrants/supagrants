# crawler.py

import asyncio
from typing import AsyncGenerator, Tuple

from phi.agent import Agent, RunResponse
from phi.tools.github import GithubTools

from .crawl4ai_tools import Crawl4aiTools  # phidata==2.7.2 broken (no AsyncWebCrawler support), crawl4i==0.4.21 broken (missing js_snippet)
from .firecrawl_tools import FirecrawlTools

from config import OPENAI_API_KEY, FIRECRAWL_API_KEY, GITHUB_ACCESS_TOKEN
from utils.llm_helper import get_llm_model



async def crawl_url_crawl4ai(url: str) -> AsyncGenerator[Tuple[str, str], None]:
    """
    Crawl the specified URL using Crawl4aiTools' async generator
    and yield each crawled page's URL and content in real time.

    :param url: The URL to crawl.

    :yield: Tuples containing (URL, page content) as strings.
    """
    if not url:
        yield ("No URL provided", "")
        return

    # Create an instance of Crawl4aiTools
    tools = Crawl4aiTools(max_length=None)

    # Use the async generator from web_crawler
    async for crawled_url, page_content in tools.web_crawler(url):
        yield crawled_url, page_content


async def crawl_url_firecrawl(url: str) -> str:
    """
    Crawl the specified URL using the Firecrawl Agent and retrieve the crawled content asynchronously.

    Args:
        url (str): The URL to be crawled.

    Returns:
        str: The content retrieved from crawling the URL. Returns `None` if no content is found.
    """
    def _crawl():
        agent = Agent(
            name="Firecrawl Agent",
            model=get_llm_model(),
            tools=[FirecrawlTools(api_key=FIRECRAWL_API_KEY, scrape=False, crawl=True)], 
            show_tool_calls=True,
            markdown=True,
        )
        
        response: RunResponse = agent.run(f"Run with the url only: {url}")
        response_dict = response.to_dict()
        messages = response_dict.get("messages", [])
        crawled_content = None
        
        for msg in messages:
            if msg.get("role") == "tool":
                crawled_content = msg.get("content")
                break
        
        return crawled_content

    crawled_content = await asyncio.to_thread(_crawl)
    return crawled_content


async def crawl_github(repo: str) -> str:
    """
    Retrieve a list of all open issues from the specified GitHub repository asynchronously.

    Args:
        repo (str): The GitHub repository in the format "owner/repo".

    Returns:
        str: A list of messages containing information about open issues.
    """
    def _crawl():
        agent = Agent(
            name="GitHub Agent",
            model=get_llm_model(),
            instructions=[
                f"This is the GitHub repo {repo}.",
                "Do not create any issues or pull requests unless explicitly asked to do so",
            ],
            tools=[GithubTools(access_token=GITHUB_ACCESS_TOKEN)],
            show_tool_calls=True,
        )
        response: RunResponse = agent.run(f"List all open issues")
        response_dict = response.to_dict()
        messages = response_dict.get("messages", [])
        return messages

    messages = await asyncio.to_thread(_crawl)  # <--- Wrapped synchronous code to run asynchronously
    return messages


if __name__ == "__main__":
    import asyncio

    async def main():
        # print(await crawl_url_crawl4ai("https://docs.ithacaprotocol.io/docs"))
        print(await crawl_url_firecrawl("https://docs.ithacaprotocol.io/docs"))
        # print(await crawl_github("phidatahq/phidata"))

    asyncio.run(main())
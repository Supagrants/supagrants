# crawler.py

from phi.agent import Agent, RunResponse
from phi.model.openai import OpenAIChat
from phi.tools.firecrawl import FirecrawlTools
from phi.tools.github import GithubTools

from crawl4ai_tools import Crawl4aiTools  # phidata==2.7.2 broken (no AsyncWebCrawler support), crawl4i==0.4.21 broken (missing js_snippet)

from config import OPENAI_API_KEY

# export FIRECRAWL_API_KEY=***
# export GITHUB_ACCESS_TOKEN=***


def crawl_url_crawl4ai(url: str) -> str:
    """
    Crawl the specified URL using the Crawl4ai Agent and retrieve the crawled content.

    This function initializes the Crawl4ai Agent with the OpenAI GPT-4 model and the Crawl4aiTools.
    It sends a request to crawl the provided URL and extracts the crawled content from the agent's response.

    Args:
        url (str): The URL to be crawled.

    Returns:
        str: The content retrieved from crawling the URL. Returns `None` if no content is found.
    """
    agent = Agent(
        name="Crawl4ai Agent",
        model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
        tools=[Crawl4aiTools(max_length=None)],
        show_tool_calls=True,
        markdown=True,
    )
    
    response: RunResponse = agent.run(f"Run with the url only: {url}")
    response_dict = response.to_dict()
    print(response_dict)
    messages = response_dict.get("messages", [])
    crawled_content = None
    
    for msg in messages:
        if msg.get("role") == "tool":
            crawled_content = msg.get("content")
            break
    
    return crawled_content


def crawl_url_firecrawl(url: str) -> str:
    """
    Crawl the specified URL using the Firecrawl Agent and retrieve the crawled content.

    This function initializes the Firecrawl Agent with the OpenAI GPT-4 model and the FirecrawlTools.
    It sends a request to crawl the provided URL and extracts the crawled content from the agent's response.

    Args:
        url (str): The URL to be crawled.

    Returns:
        str: The content retrieved from crawling the URL. Returns `None` if no content is found.
    """
    agent = Agent(
        name="Firecrawl Agent",
        model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
        tools=[FirecrawlTools(scrape=False, crawl=True)],
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


def crawl_github(repo: str) -> str:
    """
    Retrieve a list of all open issues from the specified GitHub repository.

    This function initializes the GitHub Agent with the OpenAI GPT-4 model and the GithubTools.
    It sends a request to list all open issues in the provided repository and returns the messages from the agent's response.

    Args:
        repo (str): The GitHub repository in the format "owner/repo".

    Returns:
        str: A list of messages containing information about open issues.
    """
    agent = Agent(
        name="GitHub Agent",
        model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
        instructions=[
            f"This is the GitHub repo {repo}.",
            "Do not create any issues or pull requests unless explicitly asked to do so",
        ],
        tools=[GithubTools()],
        show_tool_calls=True,
    )
    response: RunResponse = agent.run(f"List all open issues")
    response_dict = response.to_dict()
    messages = response_dict.get("messages", [])
    return messages


if __name__ == "__main__":
    print(crawl_url_crawl4ai("https://example.com/"))
    # print(crawl_url_firecrawl("https://example.com/"))
    # print(crawl_github("phidatahq/phidata"))

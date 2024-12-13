# crawler.py
from phi.agent import Agent, RunResponse
from phi.model.openai import OpenAIChat
from phi.tools.firecrawl import FirecrawlTools

from config import OPENAI_API_KEY


def crawl_url(url: str) -> str:
    """
    Crawls the given URL using the Crawler Agent and stores the result in the knowledge base.
    
    Args:
        url (str): The URL to crawl.
    
    Returns:
        str: The crawled content.
    """
    agent = Agent(
        name="Crawler Agent",
        model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
        tools=[FirecrawlTools(scrape=False, crawl=True)], 
        show_tool_calls=True, 
        markdown=True,
    )
    
    response: RunResponse = agent.run(f"this is an url: {url}")
    response_dict = response.to_dict()
    messages = response_dict.get("messages", [])
    crawled_content = None
    
    for msg in messages:
        if msg.get("role") == "tool":
            crawled_content = msg.get("content")
            break
    
    return crawled_content
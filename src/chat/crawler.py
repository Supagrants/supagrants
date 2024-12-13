from phi.agent import Agent, RunResponse
from phi.model.openai import OpenAIChat
from phi.tools.firecrawl import FirecrawlTools

from config import OPENAI_API_KEY

agent = Agent(
    name="Crawler Agent",
    model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
    tools=[FirecrawlTools(scrape=False, crawl=True)], 
    show_tool_calls=True, 
    markdown=True,
)

response: RunResponse = agent.run("this is an url: https://finance.yahoo.com/")
response_dict = response.to_dict()
messages = response_dict.get("messages")
crawled = None
for msg in messages:
    role = msg.get("role")
    content = msg.get("content")
    if role == "tool":
        crawled = content
print(crawled)
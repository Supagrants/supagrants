from phi.agent import Agent, RunResponse
from phi.model.openai import OpenAIChat

from chat.prompts import ABOUT
from config import OPENAI_API_KEY

agent = Agent(
    name="Main Agent",
    model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
    description=ABOUT,
    instructions=["role play"],
)


async def next_action(msg: str, user_id: str, mongo, reply_function=None, processing_id=None):
    response: RunResponse = agent.run(msg)
    if reply_function:
        await reply_function(response.get_content_as_string())
    return

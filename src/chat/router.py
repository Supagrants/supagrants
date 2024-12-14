from phi.agent import Agent, RunResponse
from phi.model.openai import OpenAIChat
from phi.storage.agent.postgres import PgAgentStorage
from phi.tools.duckduckgo import DuckDuckGo

from chat import prompts, knowledge
from config import OPENAI_API_KEY
from config import POSTGRES_CONNECTION


async def next_action(msg: str, user_id: str, mongo, reply_function=None, processing_id=None):
    agent = Agent(
        name="Chat Agent",
        model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
        session_id='main',# todo replace with group / chat
        user_id=user_id,
        storage=PgAgentStorage(table_name="agent_sessions", db_url=POSTGRES_CONNECTION),
        num_history_responses=10,
        description=prompts.ABOUT,
        add_datetime_to_instructions=True,
        add_history_to_messages=True,
        read_chat_history=True,
        knowledge=knowledge.pdf_knowledge_base, # todo how to combine with text_knowledge_base
        search_knowledge=True,
        tools=[DuckDuckGo()],
        telemetry=False,
    )
    response: RunResponse = agent.run(msg)
    if reply_function:
        await reply_function(response.get_content_as_string())
    return

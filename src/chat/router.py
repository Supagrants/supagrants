# router.py

import logging

from phi.agent import Agent, RunResponse, AgentMemory
from phi.memory.db.postgres import PgMemoryDb
from phi.storage.agent.postgres import PgAgentStorage
from phi.tools.duckduckgo import DuckDuckGo

from chat import prompts, knowledge
from chat.token_limit_agent import TokenLimitAgent
from chat.prompts.prompts_medium import ABOUT
from config import POSTGRES_CONNECTION
from utils.llm_helper import get_llm_model

# Setup logging
logger = logging.getLogger(__name__)

async def next_action(msg: str, user_id: str, mongo, reply_function=None, processing_id=None):
    logger.debug(f"Starting next action for user {user_id} with message: {msg[:50]}...")

    agent = TokenLimitAgent(
        name="Chat Agent",
        model=get_llm_model(),
        session_id='main',  # todo replace with group / chat
        user_id=user_id,
        # memory=AgentMemory(
        #     db=PgMemoryDb(table_name="agent_memory", db_url=POSTGRES_CONNECTION), 
        #     create_user_memories=True, 
        #     create_session_summary=True,
        #     num_memories=10,
        # ),
        storage=PgAgentStorage(table_name="agent_sessions", db_url=POSTGRES_CONNECTION),
        num_history_responses=10,
        description=ABOUT,
        add_datetime_to_instructions=True,
        add_history_to_messages=True,
        read_chat_history=True,
        knowledge=knowledge.knowledge_base,
        search_knowledge=True,
        tools=[DuckDuckGo()],
        telemetry=False,
    )
    try:
        response: RunResponse = agent.run(msg)
        logger.debug(f"Agent response generated successfully for user {user_id}.")
        
        if reply_function:
            await reply_function(response.get_content_as_string())
        
        return
    except Exception as e:
        logger.error(f"Error during agent action for user {user_id}: {str(e)}")
        raise



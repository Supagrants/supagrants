# router.py

import logging

from phi.agent import Agent, RunResponse, AgentMemory
from phi.memory.db.postgres import PgMemoryDb
from phi.storage.agent.postgres import PgAgentStorage
from phi.tools.duckduckgo import DuckDuckGo

from chat import prompts, knowledge
from chat.token_limit_agent import TokenLimitAgent
from chat.prompts.prompts_medium import ABOUT, BACKGROUND
from config import POSTGRES_CONNECTION, MAX_HISTORY
from utils.llm_helper import get_llm_model

# Setup logging
logger = logging.getLogger(__name__)

async def next_action(msg: str, user_id: str, chat_id: str, mongo, reply_function=None, processing_id=None):
    logger.info(f"Starting next action for user {user_id} with message: {msg[:50]}...")

    # Get knowledge first
    logger.info("Retrieving relevant knowledge...")
    try:
        relevant_knowledge = knowledge.knowledge_base.get_relevant_knowledge(msg)
        logger.info(f"Retrieved knowledge length: {len(relevant_knowledge) if relevant_knowledge else 0}")
        
        # Create context with the retrieved knowledge
        context = f"""
        Available Information about the user's project:
        {relevant_knowledge}

        User Query: {msg}
        """
        logger.info(f"Created context with knowledge and query")
        
    except Exception as e:
        logger.error(f"Knowledge retrieval failed: {str(e)}")
        context = msg  # Fallback to just the message if knowledge retrieval fails

    agent = TokenLimitAgent(
        name="Chat Agent",
        model=get_llm_model(),
        session_id=f"{user_id}_{chat_id}",  # Unique per chat
        user_id=user_id,
        memory=AgentMemory(
             db=PgMemoryDb(table_name="agent_memory", db_url=POSTGRES_CONNECTION), 
             create_user_memories=True, 
             create_session_summary=True,
             num_memories=10,
        ),
        storage=PgAgentStorage(table_name="agent_sessions", db_url=POSTGRES_CONNECTION),
        num_history_responses=MAX_HISTORY,
        description=f"{ABOUT}\n\nBackground Information:\n{BACKGROUND}\n\nContext:\n{relevant_knowledge}",
        add_datetime_to_instructions=True,
        add_history_to_messages=True,
        read_chat_history=True,
        knowledge=knowledge.knowledge_base,
        search_knowledge=True,
        tools=[DuckDuckGo()],
        telemetry=False,
    )
    
    try:
        logger.info("Running agent with retrieved knowledge in context")
        response: RunResponse = agent.run(context)
        logger.info(f"Agent response generated successfully for user {user_id}.")
        logger.info(f"Agent response: {response.get_content_as_string()}")
        
        if reply_function:
            await reply_function(response.get_content_as_string())
        
        return
    except Exception as e:
        logger.error(f"Error during agent action for user {user_id}: {str(e)}")
        raise

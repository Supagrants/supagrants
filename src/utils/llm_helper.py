# llm_helper.py

import logging

from phi.model.openai import OpenAIChat
from phi.model.google import Gemini
from phi.embedder.openai import OpenAIEmbedder
from utils.gemini_embedder import GeminiEmbedder
from config import OPENAI_API_KEY, OPENAI_MODEL, GOOGLE_API_KEY, LLM_PROVIDER

# Configure logger for this module
logger = logging.getLogger(__name__)

def get_llm_model():
    """
    Returns the appropriate LLM model based on the LLM_PROVIDER configuration.

    Defaults to OpenAI if LLM_PROVIDER is not set or unsupported.

    Returns:
        An instance of OpenAIChat or Gemini.

    Raises:
        ValueError: If OpenAI API key is missing when required.
    """
    # Use 'openai' as the default provider
    provider = LLM_PROVIDER.lower() if LLM_PROVIDER else "openai"

    if provider == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in config.py or environment variables.")
        logger.info("Using OpenAI LLM model.")
        return OpenAIChat(id=OPENAI_MODEL, api_key=OPENAI_API_KEY)
    elif provider == "gemini":
        logger.info("Using Gemini LLM model.")
        return Gemini(id="gemini-2.0-flash-exp", api_key=GOOGLE_API_KEY)
    else:
        # Log a warning and default to OpenAI
        logger.warning(f"Unsupported LLM_PROVIDER '{LLM_PROVIDER}'. Defaulting to OpenAI.")
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in config.py or environment variables.")
        return OpenAIChat(id=OPENAI_MODEL, api_key=OPENAI_API_KEY)


def get_embedder():
    """
    Returns the appropriate embedder based on the LLM_PROVIDER configuration.

    Defaults to OpenAIEmbedder if LLM_PROVIDER is not set or unsupported.

    Returns:
        An instance of OpenAIEmbedder or GeminiEmbedder.

    Raises:
        ValueError: If OpenAI API key is missing when required.
    """
    # Use 'openai' as the default provider
    provider = LLM_PROVIDER.lower() if LLM_PROVIDER else "openai"

    if provider == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in config.py or environment variables.")
        logger.info("Using OpenAI Embedder.")
        return OpenAIEmbedder(api_key=OPENAI_API_KEY)
    elif provider == "gemini":
        logger.info("Using Gemini Embedder.")
        return GeminiEmbedder(model="models/text-embedding-004", dimensions=768, api_key=GOOGLE_API_KEY)
    else:
        # Log a warning and default to OpenAIEmbedder
        logger.warning(f"Unsupported LLM_PROVIDER '{LLM_PROVIDER}'. Defaulting to OpenAIEmbedder.")
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in config.py or environment variables.")
        return OpenAIEmbedder(api_key=OPENAI_API_KEY)

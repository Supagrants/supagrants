"""
Primary Author(s)
Juan C. Dorado: https://github.com/jdorado/
"""
# main.py

import traceback
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel

from telegram.ext import Application

import config
from chat import router, knowledge, crawler
from utils.telegram_helper import TelegramHelper
from utils.mongo_aio import Mongo
from utils.pagerduty import sendAlert
from utils.url_helper import normalize_url

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)  # Configure logging as needed

# Initialize Application with increased connection pool size
application = (
    Application.builder()
    .token(config.TELEGRAM_BOT)
    .connection_pool_size(100)  # Adjust this number based on your requirements
    .build()
)

# Initialize TelegramHelper with the Application's Bot instance
tg = TelegramHelper(application.bot)

# Initialize MongoDB without connecting on startup
mongo = Mongo()

class TelegramUpdate(BaseModel):
    update_id: int
    message: dict

class ApiCall(BaseModel):
    token: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI.
    Handles startup and shutdown events.
    """
    logger.info("Starting up the application.")

    # Properly start the Telegram bot
    await application.initialize()
    await application.start()

    # If you have other startup tasks, do them here (Mongo connections, etc.)
    # But the prompt states "We're NOT connecting to MongoDB here as per the user's request."
    yield

    logger.info("Shutting down the application.")

    # Properly stop the Telegram bot
    await application.stop()
    await application.shutdown()

    # If you have other shutdown tasks, finalize them here.

# Assign the lifespan handler to the FastAPI app
app = FastAPI(lifespan=lifespan)

@app.post("/tasks/")
async def tasks_post():
    return {"status": "ok"}
    # await tasks.run(mongo)

@app.post("/agent/")
async def mentor(request: Request):
    text = ''
    try:
        handle = config.TELEGRAM_BOT_HANDLE
        json_data = await request.json()
        params = await tg.process_update(json_data, handle=handle)
        if not params:
            return {"status": "ok"}

        async def telegram_reply(msg):
            await tg.send_message(params['chat_id'], msg)

        # Ignore if message is from bot or no content
        if not params or params['is_bot'] or (not params['content'] and not params['file']):
            return {"status": "ok"}

        text = f"@{params['username']}: {params['content']}"
        if params['has_reply']:
            text += f" REPLYING TO: {params['reply_text']}"

        # Handle document
        if params['file']:
            await knowledge.handle_document(params['file'])
            text = f"SYSTEM: Document added to knowledge base {params['file']['file_name']}"

        # Handle URLs
        if params.get('urls'):
            logger.debug(f"Processing URLs: {params['urls']}")
            for url in params['urls']:
                normalized_url = normalize_url(url)
                if await knowledge.knowledge_base.is_duplicate(normalized_url):
                    await telegram_reply(f"URL already indexed: {url}")
                    continue

                # Start crawling and processing pages as they are yielded
                try:
                    # Initialize page count
                    page_count = 0
                    batch_size = 10  # Number of pages after which to send a Telegram message

                    # Iterate over the asynchronous generator
                    async for crawled_url, page_content in crawler.crawl_url_crawl4ai(url):
                        # Validate page content
                        if not isinstance(page_content, str):
                            logger.error(f"Page {page_count + 1} for URL {crawled_url} is not a string.")
                            continue

                        # Handle the crawled content with its specific URL
                        await knowledge.knowledge_base.handle_url(crawled_url, page_content)
                        page_count += 1

                        # Send a Telegram reply every 'batch_size' pages
                        if page_count % batch_size == 0:
                            await telegram_reply(f"{page_count} pages from the URL are indexed successfully.")

                    # After crawling completes, send a summary message if not already sent
                    if page_count % batch_size != 0:
                        await telegram_reply(f"Total {page_count} pages from the URL are indexed successfully.")
                    elif page_count == 0:
                        await telegram_reply(f"No pages were indexed from the URL: {url}")

                except Exception as e:
                    await telegram_reply(f"Failed to crawl URL: {url}. Error: {str(e)}")
                    logger.error(f"Error crawling URL {url}: {e}")
                    continue

            all_urls = ",".join(params['urls'])
            text = f"SYSTEM: URLs crawled and added to knowledge base {all_urls}"

        await router.next_action(text, params['user'], mongo,
                                 reply_function=telegram_reply,
                                 processing_id=params['message_id'])

        return {"status": "ok"}
    except Exception as e:
        await sendAlert(f"{handle}: {text} | error: {str(e)}")
        traceback.print_exc()
        return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=6010, reload=True)
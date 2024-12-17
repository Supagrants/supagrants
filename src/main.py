"""
Primary Author(s)
Juan C. Dorado: https://github.com/jdorado/
Ben Lai: https://github.com/laichunpongben/
"""
# main.py

import traceback
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel

from telegram.ext import Application

import config
from chat import router, knowledge, crawler
from utils.telegram_helper import TelegramHelper
from utils.mongo_aio import Mongo
from utils.pagerduty import sendAlert
from utils.url_helper import normalize_url

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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
async def mentor(request: Request, background_tasks: BackgroundTasks):
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
            file_info = params['file']
            mime_type = file_info.get('mime_type')
            if mime_type == 'application/pdf':
                await knowledge.knowledge_base.handle_pdf_file(file_info)
            elif mime_type == 'text/plain':
                await knowledge.knowledge_base.handle_txt_file(file_info)
            else:
                logger.warning(f"Unsupported MIME type: {mime_type}")

            text = f"SYSTEM: Document added to knowledge base {file_info['file_name']}"

        # Handle URLs
        if params.get('urls'):
            logger.debug(f"Processing URLs: {params['urls']}")

            # Initialize the crawler tool once
            crawl_tool = crawler.Crawl4aiTools()

            async def check_duplicate(url: str) -> bool:
                return await knowledge.knowledge_base.is_source_indexed(url)

            async def index_page(url: str, content: str):
                await knowledge.knowledge_base.handle_url(url, content)

            async def crawl_and_process(url: str):
                page_count = 0

                try:
                    # Create an asynchronous generator for crawling
                    crawl_generator = crawl_tool.web_crawler(
                        start_url=url,
                        is_duplicate=check_duplicate,
                        on_page_crawled=index_page,
                        max_length=crawl_tool.max_length,
                        max_depth=crawl_tool.max_depth,
                        max_pages=crawl_tool.max_pages,
                    )

                    # Iterate over the crawled pages
                    async for crawled_url, page_content in crawl_generator:
                        # Validate page content
                        if not isinstance(page_content, str):
                            logger.error(f"Page content for URL {crawled_url} is not a string.")
                            continue  # Skip invalid content

                        page_count += 1  # Increment the page count

                except Exception as e:
                    logger.error(f"Failed to crawl URL: {url}. Error: {str(e)}")

                finally:
                    # Send a single summary message after crawling completes or fails
                    if page_count > 0:
                        await telegram_reply(f"Total {page_count} pages from the URL: {url} are indexed successfully.")
                    else:
                        await telegram_reply(f"No new pages were indexed from the URL: {url}")

                    logger.info(f"Crawling completed for URL: {url} with {page_count} pages indexed.")

            # Schedule all crawl tasks to run concurrently in the background
            for url in params['urls']:
                normalized_url = normalize_url(url)
                background_tasks.add_task(crawl_and_process, normalized_url)

            all_urls = ",".join(params['urls'])
            text = f"SYSTEM: URLs are being crawled and added to knowledge base: {all_urls}"

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

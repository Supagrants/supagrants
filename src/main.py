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
import requests
import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
from telegram.ext import Application
from dotenv import load_dotenv
import json
from chat import router, knowledge, crawler
from utils.telegram_helper import TelegramHelper
from utils.mongo_aio import Mongo
from utils.pagerduty import sendAlert
from utils.url_helper import normalize_url
from utils.logging_helper import setup_logging
from config import TELEGRAM_BOT, TELEGRAM_BOT_HANDLE
from telegram import ReplyKeyboardMarkup
from utils.get_applications import get_applications
load_dotenv()

# Setup logging
logger = setup_logging(log_file='logs/main.log', level=logging.INFO)

# Initialize Application with increased connection pool size
application = (
    Application.builder()
    .token(TELEGRAM_BOT)
    .connection_pool_size(100)
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
    print("Starting up the application.")
    try:
        logger.info("Starting up the application.")

        # Properly start the Telegram bot
        await application.initialize()
        await application.start()
        yield
    finally:
        logger.info("Shutting down the application.")
        await application.stop()
        await application.shutdown()


# Assign the lifespan handler to the FastAPI app
app = FastAPI(lifespan=lifespan)


# Helper function to handle recognized commands
async def handle_menu(params, reply_function):
    """
    Handle recognized commands and display menus.
    """
    content = params['content'].strip().lower()

    # Define menus
    main_menu_buttons = [
        ["🚀 Apply for Grant", "📊 Check Application Status"],
        ["ℹ️ About Supagrants", "💡 Help", "Submit Grant"]
    ]

    # Command-based menu handling
    if content in ["/start", "start"]:
        welcome_message = (
            "👋 Welcome to Supagrants Bot!\n"
            "We help connect promising projects with grants on Solana.\n\n"
            "Select an option below to get started:"
        )
        await reply_function(
            welcome_message,
            reply_markup=ReplyKeyboardMarkup(main_menu_buttons, resize_keyboard=True)
        )
        return True
    
    if content in ["submit grant", "/submit"]:
        #find the user's project id
        logger.info(f"Getting applications for user {params['user']}")
        application = await get_applications(params['user'])
        
        # Convert application data to JSON-serializable format
        json_data = {
            "application": json.dumps(application, default=str)  # Use default=str to handle datetime
        }
        
        url = "https://supagrant-funder-production.up.railway.app/submit/"
        response = requests.post(url, json=json_data)
        logger.info(f"Response from funder agent: {response.json()}")
        await reply_function(
                """
                Awesome! We're submitting your grant application.
                """
            )
        return True

    if content in ["🚀 apply for grant", "/apply"]:
        await reply_function(
            """
            👋 Welcome to Supagrants Bot! I'm here to help you secure funding for your Solana project.

            To start your grant application, please share:
            1️⃣ Your project's website URL - This helps us understand your online presence
            2️⃣ Your pitch deck (PDF) - This gives us detailed insight into your project

            You can share either one now, and I'll help you with the next steps. Ready to begin? 🚀

            💡 Tip: For the best results, make sure your pitch deck includes key information about your project's goals, team, and funding needs.
            """
        )
        return True

    if content in ["📊 check application status", "/status"]:
        await reply_function("You selected 'Check Application Status'. Please provide your application ID.")
        return True

    if content in ["ℹ️ about supagrants", "/about"]:
        about_text = (
            "ℹ️ Supagrants is an AI-powered grant application assistant for the Solana ecosystem.\n\n"
            "We help:\n- Match projects with suitable grants\n"
            "- Streamline the application process\n"
            "- Provide real-time status updates\n\n"
            "Find more info on: [https://supagrants.example.com](https://supagrants.example.com)"
        )
        await reply_function(about_text)
        return True

    if content in ["💡 help", "/help"]:
        help_text = (
            "💡 Here's how to use Supagrants Bot:\n\n"
            "/start - Return to main menu\n"
            "/apply - Start a new grant application\n"
            "/status - Check your application status\n"
            "/about - Learn about Supagrants\n"
            "/help - Show this help message\n\n"
            "Need more assistance? Type your question below."
        )
        await reply_function(help_text)
        return True

    if content == "/cancel":
        await reply_function(
            "🛑 Current process has been cancelled.\n"
            "You can start a new process or return to the main menu.",
            reply_markup=ReplyKeyboardMarkup(main_menu_buttons, resize_keyboard=True)
        )
        return True

    return False  #


@app.post("/agent/")
async def mentor(request: Request, background_tasks: BackgroundTasks):
    text = ''
    try:
        handle = TELEGRAM_BOT_HANDLE
        json_data = await request.json()
        params = await tg.process_update(json_data, handle=handle)
        if not params:
            return {"status": "ok"}

        async def telegram_reply(msg, reply_markup=None):
            await tg.send_message_with_retry(params['chat_id'], msg, reply_markup=reply_markup)

        # Ignore if message is from bot or no content
        if not params or params['is_bot'] or (not params['content'] and not params['file']):
            return {"status": "ok"}

        # Check if input is a recognized command and handle the menu
        if await handle_menu(params, telegram_reply):
            return {"status": "ok"}  # Command handled; stop further processing

        # Handle other inputs like URLs or files
        text = f"@{params['username']}: {params['content']}"
        if params['has_reply']:
            text += f" REPLYING TO: {params['reply_text']}"

        # Handle document uploads
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

        # Proceed with general next action
        await router.next_action(text, params['user'], params['chat_id'], mongo,
                                 reply_function=telegram_reply,
                                 processing_id=params['message_id'])

        return {"status": "ok"}
    except Exception as e:
        await sendAlert(f"{handle}: {text} | error: {str(e)}")
        traceback.print_exc()
        return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=6010,
        reload=True,
        log_config=None
    )

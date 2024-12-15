"""
Primary Author(s)
Juan C. Dorado: https://github.com/jdorado/
"""
# main.py

import traceback
import asyncio
import logging

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel

import config
from chat import router, knowledge, crawler
from utils import telegram_helper
from utils.mongo_aio import Mongo
from utils.pagerduty import sendAlert

logger = logging.getLogger(__name__)

app = FastAPI()
mongo = Mongo()
tg = telegram_helper.TelegramHelper(config.TELEGRAM_BOT)


class TelegramUpdate(BaseModel):
    update_id: int
    message: dict


class ApiCall(BaseModel):
    token: str


@app.post("/tasks/")
async def tasks_post():
    return "ok"
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

        # ignore if message is from bot or no content
        if not params or params['is_bot'] or (not params['content'] and not params['file']):
            return

        text = f"@{params['username']}: {params['content']}"
        if params['has_reply']:
            text += f" REPLYING TO: {params['reply_text']}"

        # Handle document
        if params['file']:
            await knowledge.handle_document(params['file'])
            text = f"SYSTEM: Document added to knowledge base {params['file']['file_name']}"

        # Handle URLs
        if len(params['urls']) > 0:
            logger.debug(f"Processing URLs: {params['urls']}")
            for url in params['urls']:
                if await knowledge.knowledge_base.is_duplicate(url):
                    await telegram_reply(f"URL already indexed: {url}")
                    continue

                crawled_content = await crawler.crawl_url_crawl4ai(url)

                # Ensure crawled_content is a string
                if isinstance(crawled_content, list):
                    crawled_content = ' '.join(crawled_content)
                    logger.debug(f"Joined crawled_content into string: {crawled_content}")

                if not isinstance(crawled_content, str):
                    await telegram_reply(f"Failed to crawl URL (invalid content): {url}")
                    logger.error(f"crawled_content is not a string for URL {url}.")
                    continue

                await knowledge.knowledge_base.handle_url(url, crawled_content)
                await telegram_reply(f"URL indexed successfully: {url}")

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

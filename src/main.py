"""
Primary Author(s)
Juan C. Dorado: https://github.com/jdorado/
"""

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel
import traceback
import config
from utils import telegram
from utils.mongo_aio import Mongo
from utils.pagerduty import sendAlert

app = FastAPI()
mongo = Mongo()


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
        handle = config.TELEGRAN_BOT_HANDLE
        update = await request.json()
        params = await telegram.process_update(update, handle=handle)

        async def telegram_reply(msg):
            await telegram.send_message_to_telegram(config.TELEGRAM_BOT, params['chat_id'], msg)

        # ignore if message is from bot or no content
        if not params or params['is_bot'] or not params['content']:
            return

        is_directed_to_bot = params['reply_user'] == handle.replace('@', '') or params['has_mention'] or params[
            'chat_type'] == 'private'

        # if is a reply to another user, skip
        # NOTE: Telegram has a bug where replying to another user is not detected as a reply
        is_replying_someone_else = params['has_reply'] and params['reply_user'] != handle.replace('@', '')
        if is_replying_someone_else and not is_directed_to_bot:
            return

        text = f"@{params['username']}: {params['content']}"
        if params['has_reply']:
            text += f" REPLYING TO: {params['reply_text']}"

        # todo
        await telegram_reply(text)
        return "ok"
        # await agent.next_action(text, params['user'], mongo,
        #                                reply_function=telegram_reply,
        #                                processing_id=params['message_id'])

        return {"status": "ok"}
    except Exception as e:
        await sendAlert(f"{handle}: {text} | error: {str(e)}")
        traceback.print_exc()
        return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=6020, reload=True)

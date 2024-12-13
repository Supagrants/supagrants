"""
Primary Author(s)
Juan C. Dorado: https://github.com/jdorado/
"""

import traceback

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel

import config
from chat import router, knowledge
from utils import telegram_helper
from utils.mongo_aio import Mongo
from utils.pagerduty import sendAlert

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
        handle = config.TELEGRAN_BOT_HANDLE
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

        # handle document
        if params['file']:
            output = await knowledge.handle_document(params['file'])

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

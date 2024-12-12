"""
v1.0
"""
import os

import PyPDF2
import aiohttp
from chatgpt_md_converter import telegram_format

from config import logger
from utils import fetch

TELEGRAM_API_URL = "https://api.telegram.org/bot"
DOWNLOAD_DIR = "./files"

"""
# Telegram chatbot
# curl -X POST "https://api.telegram.org/bot<your_bot_token>/setWebhook?url=https://your-domain.com/webhook/"
https://core.telegram.org/bots
"""


async def send_message_to_telegram(bot: str, chat_id: int, text: str):
    url = f"{TELEGRAM_API_URL}{bot}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": telegram_format(text),
        "parse_mode": "HTML"
    }
    await fetch.post(url, payload)


async def typing_action(bot: str, chat_id: int):
    url = f"{TELEGRAM_API_URL}{bot}/sendChatAction"
    payload = {
        "chat_id": chat_id,
        "action": "typing"
    }
    await fetch.post(url, payload)


async def download_file(bot, file_id, file_name, save=False):
    file_path = await get_file_path(bot, file_id)
    local_file_path = os.path.join(DOWNLOAD_DIR, file_name)
    if save:
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)
    data = await get_file(file_path, local_file_path, save_locally=save)
    logger.info(f"Downloaded: {local_file_path}")
    return data


async def get_file_path(bot, file_id):
    url = f"{TELEGRAM_API_URL}{bot}/getFile?file_id={file_id}"
    response = await fetch.get(url)
    return response['result']['file_path']


async def get_file(bot, file_path, local_filename='./tmp_file', save_locally=False):
    try:
        url = f"https://api.telegram.org/file/bot{bot}/{file_path}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    file_content = bytearray()  # To store the file content in memory

                    # If save_locally is True, write to the file
                    if save_locally:
                        with open(local_filename, 'wb') as file:
                            while True:
                                chunk = await response.content.read(1024)  # Read in chunks
                                if not chunk:
                                    break
                                file.write(chunk)  # Write to the local file
                                file_content.extend(chunk)  # Add chunk to bytearray
                    else:
                        # Only read the content into memory, don't save locally
                        while True:
                            chunk = await response.content.read(1024)  # Read in chunks
                            if not chunk:
                                break
                            file_content.extend(chunk)  # Add chunk to bytearray

                    return file_content  # Return the file content
                else:
                    logger.error(f"Failed to download the file, status code: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error downloading file: {e} {file_path}")
        raise e


async def process_update(update: dict, handle='') -> dict:
    try:
        if 'message' in update:
            message = update['message']
            chat = message['chat']
            from_user = message['from']
            content = message.get('text', '')
            reply = message.get('reply_to_message', None)
            new_chat_members = message.get('new_chat_members', None)
            'new_chat_members'
            has_reply = False
            has_mention = handle in content

            # remove handle
            if handle:
                content = content.replace(handle, '').strip()

            # only new members, greet them
            if new_chat_members and not content:
                users = [f"@{user['username']}" for user in new_chat_members]
                content = f"Welcome {', '.join(users)} to the group!"

            if reply:
                has_reply = True

            return {
                "message_id": update['update_id'],
                "content": content,
                "user": str(from_user['id']),
                "is_bot": from_user['is_bot'],
                "first_name": from_user.get('first_name'),
                "last_name": from_user.get('last_name'),
                "username": from_user.get('username'),
                "chat_type": chat['type'],
                "chat_id": chat['id'],
                "chat_title": chat.get('title'),  # Only present for groups
                "has_mention": has_mention,
                "has_reply": has_reply,
                'reply_text': message['reply_to_message']['text'] if has_reply else '',
                'reply_user': message['reply_to_message']['from']['username'] if has_reply else ''
            }

        else:
            raise KeyError("Update contains neither 'message' nor 'my_chat_member' field")

    except KeyError as e:
        logger.info(f"Missing required field in Telegram payload")
        return


async def process_update2(bot, update):
    if update.message['from']['is_bot']:
        return {"status": "error", "message": "Bot message"}

    message = update.message
    chat_id = message['chat']['id']
    content = ''

    # handle file if received
    if 'document' in message:
        mime_type = message['document']['mime_type']
        file_id = message['document']['file_id']
        file_name = message['document']['file_name']
        caption = message.get('caption') if message.get('caption') else ''

        # check valid types
        if mime_type in ['application/pdf', 'text/plain']:
            data = await download_file(bot, file_id, file_name)

            # If the file is a text file, decode it as text
            if mime_type == 'text/plain':
                content = caption + "\n" + data.decode('utf-8')  # Decode bytearray to string
                logger.info(f"Text file as input: {file_name}")

            # If the file is a PDF, extract text using a PDF extraction method
            elif mime_type == 'application/pdf':
                content = caption + "\n" + extract_text_from_pdf(data)
                logger.info(f"PDF file as input: {file_name}")

    # handle images
    if 'photo' in message:
        # file_id = message['photo'][-1]['file_id']
        # file_name = f"{file_id}.jpg"
        # await telegram.download_file(file_id, file_name)
        # todo how to handle
        pass

    if 'video' in message:
        # file_id = message['video']['file_id']
        # file_name = message['video']['file_name']
        # await telegram.download_file(file_id, file_name)
        # todo how to handle
        pass

    # get agent router response
    if 'text' in message:
        content = message['text']
        if 'reply_to_message' in message:
            content += "\n" + message['reply_to_message']['text']

    return {
        "message_id": update.update_id,
        "content": content,
        "chat_id": chat_id,
        "user": str(chat_id),
        "first_name": message['chat'].get('first_name'),
        "last_name": message['chat'].get('last_name'),
        "username": message['from'].get('username'),
    }

    # reply = await router.next_action(content, str(chat_id), mongo, first_name=message['chat'].get('first_name'))
    # await send_message_to_telegram(bot, chat_id, reply)
    # return {"status": "ok"}


def extract_text_from_pdf(data):
    from io import BytesIO
    pdf_text = ''

    # Load the byte data into a BytesIO object
    with BytesIO(data) as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            pdf_text += page.extract_text()

    return pdf_text

# utils/telegram_helper.py

import os
import re
import logging
from typing import Optional
import asyncio

from telegram import Update, Bot, MessageEntity
from telegram.constants import ParseMode
from chatgpt_md_converter import telegram_format

from utils.url_helper import is_valid_url, extract_valid_urls

logger = logging.getLogger(__name__)

class TelegramHelper:
    def __init__(self, bot: Bot, download_dir: str = "./files", rate_limit: int = 20):
        """
        Initialize TelegramHelper with an existing Bot instance.

        Args:
            bot (Bot): An instance of telegram.Bot configured with desired settings.
            download_dir (str): Directory to download files. Defaults to "./files".
            rate_limit (int): Maximum number of concurrent send_message operations.
        """
        self.bot = bot
        self.DOWNLOAD_DIR = download_dir
        if not os.path.exists(self.DOWNLOAD_DIR):
            os.makedirs(self.DOWNLOAD_DIR)
        
        # Initialize semaphore for rate limiting
        self.rate_limiter = asyncio.Semaphore(rate_limit)

    async def send_message(self, chat_id: int, text: str) -> None:
        """
        Send a message using the external telegram_format converter with rate limiting.

        Args:
            chat_id (int): The chat ID to send the message to.
            text (str): The message text.
        """
        formatted_text = telegram_format(text)
        async with self.rate_limiter:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=formatted_text,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send message to chat {chat_id}: {e}")
                raise

    async def process_update(
            self,
            update_data: dict,
            handle: str = ''
    ) -> Optional[dict]:
        """
        Process a Telegram update and return structured data.

        Args:
            update_data (dict): The update data received from Telegram.
            handle (str): Optional handle to filter messages.

        Returns:
            Optional[dict]: Structured data extracted from the update.
        """
        try:
            update = Update.de_json(update_data, self.bot)
            message = update.effective_message
            if not message:
                return None

            content = message.text or message.caption or ''

            if handle and handle in content:
                content = content.replace(handle, '').strip()

            # Extract URLs from message entities
            entity_urls = []
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntity.URL:
                        url = message.parse_entity(entity)
                        entity_urls.append(url)
                    elif entity.type == MessageEntity.TEXT_LINK:
                        url = entity.url
                        entity_urls.append(url)

            # Use the helper function to extract and validate URLs
            extracted_urls = extract_valid_urls(content, entity_urls)

            file_info = None
            if message.document:
                file = await message.document.get_file()
                file_info = {
                    'file_id': message.document.file_id,
                    'file_name': message.document.file_name,
                    'mime_type': message.document.mime_type,
                    'file_size': message.document.file_size,
                    'file_url': file.file_path
                }
            elif message.photo:
                photo = message.photo[-1]
                file = await photo.get_file()
                file_info = {
                    'file_id': photo.file_id,
                    'file_name': f"{photo.file_id}.jpg",
                    'mime_type': 'image/jpeg',
                    'file_size': photo.file_size,
                    'file_url': file.file_path
                }
            elif message.video:
                file = await message.video.get_file()
                file_info = {
                    'file_id': message.video.file_id,
                    'file_name': message.video.file_name,
                    'mime_type': message.video.mime_type,
                    'file_size': message.video.file_size,
                    'file_url': file.file_path
                }

            new_members = [
                member.to_dict() for member in message.new_chat_members
            ] if message.new_chat_members else []

            return {
                "message_id": update.update_id,
                "content": content,
                "file": file_info,
                "user": str(message.from_user.id),
                "is_bot": message.from_user.is_bot,
                "username": message.from_user.username,
                "chat_id": message.chat.id,
                "chat_type": message.chat.type,
                "chat_title": message.chat.title,
                "has_mention": bool(handle and handle in content),
                "has_reply": bool(message.reply_to_message),
                "reply_text": message.reply_to_message.text if message.reply_to_message else '',
                "reply_user": message.reply_to_message.from_user.username if message.reply_to_message else '',
                "new_members": new_members,
                "has_new_members": bool(new_members),
                "urls": extracted_urls,
            }

        except Exception as e:
            logger.error(f"Error processing update: {e}")
            return None

import psycopg2
import json
import hashlib
import logging

from config import POSTGRES_CONNECTION
from utils.llm_helper import get_embedder

logger = logging.getLogger(__name__)


async def save_response(response: str, user_id: str, chat_id: str):
    """
    Save response directly to ai.applications table.
    Updates existing record if user_id exists.
    """
    try:
        # Get embedding for the response
        embedder = get_embedder()
        embedding = embedder.get_embedding(response)
        
        # Generate a content hash
        response_bytes = response.encode('utf-8')
        content_hash = hashlib.md5(response_bytes).hexdigest()
        
        # Basic metadata
        meta_data = {
            "source": f"chat_{chat_id}",
            "user_id": user_id,
            "chat_id": chat_id
        }

        # Create connection
        conn = psycopg2.connect(POSTGRES_CONNECTION)
        cur = conn.cursor()

        # First check if user_id exists
        check_query = """
        SELECT id FROM ai.applications 
        WHERE meta_data->>'user_id' = %s 
        ORDER BY created_at DESC 
        LIMIT 1
        """
        cur.execute(check_query, (user_id,))
        existing_record = cur.fetchone()

        if existing_record:
            # Update existing record
            update_query = """
            UPDATE ai.applications 
            SET 
                content = %s,
                meta_data = %s,
                embedding = %s,
                content_hash = %s,
                updated_at = NOW()
            WHERE id = %s
            """
            
            update_values = (
                response,                          # content
                json.dumps(meta_data),             # meta_data
                embedding,                         # embedding
                content_hash,                      # content_hash
                existing_record[0]                 # id
            )
            
            cur.execute(update_query, update_values)
            logger.info(f"Updated existing application for user {user_id}")
        else:
            # Insert new record
            insert_query = """
            INSERT INTO ai.applications (
                id,
                name,
                content,
                meta_data,
                embedding,
                document_type,
                content_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            insert_values = (
                content_hash,                      # id
                f"Application Response - {user_id}",  # name
                response,                          # content
                json.dumps(meta_data),             # meta_data
                embedding,                         # embedding
                "application",                     # document_type
                content_hash                       # content_hash
            )
            
            cur.execute(insert_query, insert_values)
            logger.info(f"Inserted new application for user {user_id}")

        conn.commit()
        cur.close()
        conn.close()
            
        return content_hash
        
    except Exception as e:
        logger.error(f"Error saving application response: {str(e)}")
        raise


async def get_applications(user_id: str):
    """
    Get the latest application for a specific user.
    
    Args:
        user_id (str): Telegram user ID

    Returns:
        dict: Details of the latest application
    """
    try:
        # Create connection
        conn = psycopg2.connect(POSTGRES_CONNECTION)
        cur = conn.cursor()

        # Query to get the latest application
        query = """
        SELECT 
            id,
            name,
            content,
            meta_data,
            document_type,
            created_at
        FROM ai.applications 
        WHERE meta_data->>'user_id' = %s 
        ORDER BY created_at DESC
        LIMIT 1
        """
        
        cur.execute(query, (user_id,))
        application = cur.fetchone()

        # Format the result
        if application:
            latest_application = {
                "id": application[0],
                "name": application[1],
                "content": application[2],
                "meta_data": application[3],
                "document_type": application[4],
                "created_at": application[5].isoformat() if application[5] else None
            }
        else:
            latest_application = None

        cur.close()
        conn.close()

        logger.info(f"Retrieved latest application for user {user_id}")
        return latest_application

    except Exception as e:
        logger.error(f"Error retrieving applications for user {user_id}: {str(e)}")
        raise
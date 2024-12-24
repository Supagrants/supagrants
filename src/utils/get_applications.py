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

            # Insert query
            query = """
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
            
            values = (
                content_hash,                      # id
                f"Application Response - {user_id}",  # name
                response,                          # content
                json.dumps(meta_data),             # meta_data
                embedding,                         # embedding
                "application",                     # document_type
                content_hash                       # content_hash
            )
            
            cur.execute(query, values)
            conn.commit()
            
            cur.close()
            conn.close()
                
            logger.info(f"Saved application response for user {user_id}")
            return content_hash
            
        except Exception as e:
            logger.error(f"Error saving application response: {str(e)}")
            raise


async def get_applications(user_id: str):
    """
    Get all applications for a specific user.
    
    Args:
        user_id (str): Telegram user ID

    Returns:
        list: List of applications with their details
    """
    try:
        # Create connection
        conn = psycopg2.connect(POSTGRES_CONNECTION)
        cur = conn.cursor()

        # Query to get applications
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
        """
        
        cur.execute(query, (user_id,))
        applications = cur.fetchall()

        # Format the results
        formatted_applications = []
        for app in applications:
            formatted_app = {
                "id": app[0],
                "name": app[1],
                "content": app[2],
                "meta_data": app[3],
                "document_type": app[4],
                "created_at": app[5].isoformat() if app[5] else None
            }
            formatted_applications.append(formatted_app)

        cur.close()
        conn.close()

        logger.info(f"Retrieved {len(formatted_applications)} applications for user {user_id}")
        return formatted_applications

    except Exception as e:
        logger.error(f"Error retrieving applications for user {user_id}: {str(e)}")
        raise